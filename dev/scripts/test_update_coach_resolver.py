"""`/update_coach` resolver: pick the session, then decide FASTER or not.

Pins the gate the skill depends on, because a wrong "yes" silently overwrites a
curated reference lap and coaching model:

1. **Discovery is order-independent.** "car + track" and "track + car" describe
   the same combo; spaced/accented/punctuated spellings land on the same slugs.
2. **The age window is real.** `--within` drops stale recordings instead of
   quietly using the newest file on disk.
3. **Ambiguity stops instead of guessing.** Two combos in the window is an ASK.
4. **The verdict is the exit code.** FASTER/NO_REFERENCE -> 0, NOT_FASTER -> 3,
   ASK -> 2 — and the script never writes to the reference directory.
5. **Multi-shard recordings are one session.**

Lap times are synthesised, but through the same `find_complete_laps` guards the
exporter uses (session_time_s / lap_time_s / lap_distance_m consistency).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.agents/skills/update-coach/scripts/find_candidate_session.py'
SAMPLES_PER_LAP = 200
passed = failed = 0


def ok(value, label):
    global passed, failed
    passed += bool(value)
    failed += not bool(value)
    print(f'[{"PASS" if value else "FAIL"}] {label}')


def lap_table(laps: list[tuple[int, float]]) -> pa.Table:
    """Consecutive laps; `lap_time_s` climbs 0→T, `session_time_s` rides the ET clock."""
    lap_numbers, lap_times, session_times, distances = [], [], [], []
    et = 0.0
    for lap_number, duration in laps:
        for i in range(SAMPLES_PER_LAP):
            fraction = i / (SAMPLES_PER_LAP - 1)
            lap_numbers.append(lap_number)
            lap_times.append(duration * fraction)
            session_times.append(et + duration * fraction)
            distances.append(5000.0 * fraction)
        et += duration
    return pa.table({
        'lap_number': pa.array(lap_numbers, pa.int32()),
        'lap_time_s': pa.array(lap_times, pa.float32()),
        'session_time_s': pa.array(session_times, pa.float64()),
        'lap_distance_m': pa.array(distances, pa.float32()),
    })


def write_session(directory: Path, stem: str, laps, track: str, vehicle: str,
                  started: datetime, shards: int = 1) -> None:
    if shards == 1:
        pq.write_table(lap_table(laps), directory / f'{stem}.parquet')
    else:
        per_shard = max(1, len(laps) // shards)
        for index in range(shards):
            chunk = laps[index * per_shard:(index + 1) * per_shard]
            if chunk:
                pq.write_table(lap_table(chunk), directory / f'{stem}.part{index + 1:02d}.parquet')
    stamp = started.strftime('%Y-%m-%dT%H:%M:%SZ')
    sidecar = {'schema_version': '2', 'track': track, 'vehicle_name': vehicle,
               'session_type_label': 'practice', 'started_utc': stamp, 'ended_utc': stamp}
    (directory / f'{stem}.json').write_text(json.dumps(sidecar), encoding='utf-8')


def run(*args: str):
    proc = subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=ROOT)
    payload = None
    if '\n{' in proc.stdout:
        payload = json.loads(proc.stdout[proc.stdout.index('\n{'):])
    return proc.returncode, proc.stdout + proc.stderr, payload


def reference_file(refs: Path, track: str, vehicle: str, text: str) -> None:
    pq.write_table(lap_table([(1, 0.001)]), refs / f'{track}_{vehicle}_time_{text}.parquet')


BARCELONA = 'Circuit de Barcelona'
GINETTA = 'DKR Engineering #4:ELMS25'
TRACK = 'circuit-de-barcelona'
CAR = 'dkr-engineering-4-elms25'
NOW = datetime.now(timezone.utc).replace(microsecond=0)

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    sessions, refs = base / 'sessions', base / 'refs'
    sessions.mkdir()
    refs.mkdir()

    write_session(sessions, 'session_20261114T064918Z_circuit-de-barcelona_lmu_practice',
                  [(1, 97.2), (2, 95.5), (3, 96.1)], BARCELONA, GINETTA, NOW - timedelta(minutes=10))
    write_session(sessions, 'session_20261113T184458Z_monza_lmu_practice',
                  [(1, 108.0)], 'Autodromo Nazionale Monza', GINETTA, NOW - timedelta(minutes=20))
    write_session(sessions, 'session_20260101T100000Z_circuit-de-barcelona_lmu_practice',
                  [(1, 92.0)], BARCELONA, GINETTA, NOW - timedelta(days=30))
    write_session(sessions, 'session_20261114T070000Z_circuit-de-barcelona_lmu_practice',
                  [(1, 101.0), (2, 99.8), (3, 100.4), (4, 99.9)],
                  BARCELONA, GINETTA, NOW - timedelta(minutes=2), shards=2)  # 2 shards

    common = ['--sessions-dir', str(sessions), '--refs-dir', str(refs), '--json']
    reference_file(refs, TRACK, CAR, '01.36.040')  # 96.040 s

    # 1 + 7. Order independence, and the fresh session wins the window.
    code_a, out_a, json_a = run('--car', 'Ginetta', '--track', 'Barcelona',
                                '--within', '1h', *common)
    code_b, out_b, json_b = run('--track', 'circuit de barcelona', '--car', 'dkr-engineering',
                                '--within', '1h', *common)
    ok(code_a == 0, f'car+track resolves and proceeds → exit {code_a}')
    ok(json_a and json_a['verdict'] == 'FASTER', f"verdict FASTER → {json_a and json_a['verdict']}")
    ok(json_a and json_a['track'] == TRACK and json_a['vehicle_slug'] == CAR,
       f"combo is {TRACK}/{CAR} → {json_a and (json_a['track'], json_a['vehicle_slug'])}")
    ok(json_a and json_a['reference']['time_s'] == 96.04,
       f"reference read from filename → {json_a and json_a['reference']}")
    ok(json_a == json_b, 'car+track and track+car are the same query')
    ok(json_a and json_a['fastest']['time_s'] == 95.5,
       f"fastest complete lap 95.5 s → {json_a and json_a['fastest']}")
    ok(json_a and len(json_a['sessions']) == 3
       and sum('.part' in p for p in json_a['sessions']) == 2,
       f"multi-shard recording stays one candidate (3 files, 2 recordings) → "
       f"{json_a and len(json_a['sessions'])}")
    ok(json_a and json_a['catalog_slug'] == 'ginetta-lmp3',
       f"catalog slug resolved (bug 27) → {json_a and json_a['catalog_slug']}")

    # 2. The 30-day-old 92.0 s recording is outside the window, so it cannot win.
    ok(json_a['fastest']['time_s'] != 92.0,
       f"stale 92.0 s recording stays out of the window → {json_a['fastest']}")
    code_wide, out_wide, json_wide = run('--car', 'Ginetta', '--track', 'Barcelona',
                                         '--within', '40d', *common)
    ok(json_wide and json_wide['fastest']['time_s'] == 92.0,
       f"widening the window admits it → {json_wide and json_wide['fastest']}")

    # 3. Ambiguity and emptiness are ASK, never a guess.
    code_amb, out_amb, json_amb = run('--car', 'Ginetta', '--within', '1h', *common)
    ok(code_amb == 2 and json_amb is None, f'multi-track match asks → exit {code_amb}')
    ok('AMBIGUOUS' in out_amb, 'ambiguity is named in the output')
    code_none, out_none, _ = run('--car', 'Ferrari', '--within', '1h', *common)
    ok(code_none == 2 and 'NO_SESSION' in out_none, f'no match asks → exit {code_none}')
    code_tight, out_tight, _ = run('--car', 'Ginetta', '--track', 'Barcelona',
                                   '--within', '60s', *common)
    ok(code_tight == 2 and 'NO_SESSION' in out_tight, f'empty window asks → exit {code_tight}')

    # 4. NOT_FASTER changes nothing: the reference must be faster than 95.5 s.
    reference_file(refs, TRACK, CAR, '01.33.000')  # 93.000 s
    before = sorted(p.name for p in refs.iterdir())
    code_slow, out_slow, json_slow = run('--car', 'Ginetta', '--track', 'Barcelona',
                                         '--within', '1h', *common)
    ok(code_slow == 3, f'NOT_FASTER exits 3 → {code_slow}')
    ok(json_slow and json_slow['verdict'] == 'NOT_FASTER',
       f"verdict NOT_FASTER → {json_slow and json_slow['verdict']}")
    ok(sorted(p.name for p in refs.iterdir()) == before,
       'resolver never writes to the reference directory')

    # An equal lap is not faster (1 ms margin keeps the gate idempotent).
    reference_file(refs, TRACK, CAR, '01.35.500')  # exactly 95.500 s
    code_equal, _, json_equal = run('--car', 'Ginetta', '--track', 'Barcelona', '--within', '1h', *common)
    ok(code_equal == 3 and json_equal['verdict'] == 'NOT_FASTER',
       f'equal lap keeps the reference → exit {code_equal}')

    # 5. No reference on disk → export it (pipeline A / B decided by the model).
    empty_refs = base / 'empty-refs'
    empty_refs.mkdir()
    code_new, out_new, json_new = run('--sessions-dir', str(sessions), '--car', 'Ginetta',
                                      '--track', 'Barcelona', '--within', '1h',
                                      '--refs-dir', str(empty_refs), '--json')
    ok(code_new == 0 and json_new['verdict'] == 'NO_REFERENCE',
       f'NO_REFERENCE proceeds → {json_new and json_new["verdict"]}')
    ok(json_new['pipeline'] == 'B' and json_new['coaching_model']['exists'] is True,
       f"pipeline B because a curated model exists → {json_new and json_new['pipeline']}")

    # 6. Explicit --session wins over discovery and the age window.
    explicit = sorted(sessions.glob('session_20260101T100000Z*.parquet'))
    code_exp, out_exp, json_exp = run('--session', *[str(p) for p in explicit],
                                      '--refs-dir', str(refs), '--json')
    ok(code_exp == 0 and json_exp['fastest']['time_s'] == 92.0,
       f'explicit session bypasses --within → {json_exp and json_exp["fastest"]}')

    # 7. A recording with no complete lap is an ASK, not "0.0 s is fastest".
    short = base / 'short'
    short.mkdir()
    write_session(short, 'session_20261114T080000Z_circuit-de-barcelona_lmu_practice', [(1, 40.0)], BARCELONA, GINETTA, NOW)
    code_short, out_short, _ = run('--sessions-dir', str(short), '--car', 'Ginetta', '--json')
    ok(code_short == 2 and 'NO_LAPS' in out_short,
       f'laps under the 60 s guard ask instead of winning → exit {code_short}')

print(f'\n  {passed}/{passed + failed} assertions passed')
sys.exit(1 if failed else 0)
