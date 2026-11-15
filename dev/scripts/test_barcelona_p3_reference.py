"""Slice 57: guarded Barcelona/P3 quali reference and complete-lap selection."""
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'product/python'))
from lap_telemetry.coach.reference_resolver import resolve_reference_lap
from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.track_model_resolver import resolve_track_model
from lap_telemetry.parquet_utils import build_segments

TRACK = 'circuit-de-barcelona'
CAR = 'dkr-engineering-4-elms25'
VEHICLE = 'DKR Engineering #4:ELMS25'
MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{CAR}.json'
REF_NAME = f'{TRACK}_{CAR}_time_01.36.040.parquet'
SESSION = ROOT / 'sessions/session_20261115T183239Z_circuit-de-barcelona_lmu_quali.parquet'
# id, existing long name, spoken short name, reviewed entry/apex/exit.
# Retain the legacy model's naming and IDs; this is not a renumbering slice.
ZONES = [
    ('t1', 'Turn 1 — Elf', 'Elf', (820, 842, 869)),
    ('t2', 'Turn 2', '2', (909, 940, 972)),
    ('t3', 'Turn 3 — Renault', 'Renault', (1073, 1167, 1172)),
    ('t4', 'Turn 4 — Repsol', 'Repsol', (1708, 1731, 1775)),
    ('t5', 'Turn 5 — Seat', 'Seat', (2093, 2143, 2166)),
    ('t6', 'Turn 7', '7', (2518, 2568, 2575)),
    ('t7', 'Turn 8', '8', (2832, 2850, 2850)),
    ('t8', 'Turn 9 — Campsa', 'Campsa', (2851, 2923, 2925)),
    ('t9', 'Turn 10 — La Caixa', 'La Caixa', (3496, 3508, 3525)),
    ('t10', 'Turn 12', 'Twelve', (3782, 3785, 3846)),
    ('t11', 'Turn 13', 'Thirteen', (3989, 4033, 4034)),
    ('t12', 'Turn 14', 'Fourteen', (4337, 4343, 4343)),
]
passed = failed = 0


def ok(value, label):
    global passed, failed
    passed += bool(value)
    failed += not bool(value)
    print(f'[{"PASS" if value else "FAIL"}] {label}')


def main():
    refs = list((ROOT / 'product/data/reference-laps').glob(f'{TRACK}_{CAR}_time_*.parquet'))
    ok(len(refs) == 1, 'exactly one Barcelona/P3 reference')
    ok(refs and refs[0].name == REF_NAME, 'qualifying reference is 1:36.040')
    if not refs:
        return
    raw = json.loads(MODEL.read_text(encoding='utf-8'))
    model = load_track_coaching_model(MODEL)
    table = pq.read_table(refs[0])
    ok(raw['reference_lap']['path'] == f'product/data/reference-laps/{REF_NAME}',
       'model points to the new reference with a portable path')
    ok(raw['reference_lap']['lap_time_s'] == 96.040, 'model authoritative time updated')
    metadata = table.schema.metadata or {}
    ok(float(metadata.get(b'authoritative_lap_time_s', b'nan')) == 96.040,
       'export metadata stores authoritative 96.040 seconds')
    ok(table.num_rows == 4790, 'exact selected segment contains 4790 rows')
    ok(len(build_segments(table['lap_number'].to_pylist())) == 1,
       'reference is a single contiguous segment')
    ok(set(table['lap_number'].to_pylist()) == {4}, 'qualifying lap 4 selected')
    ok(all(table['lap_valid'].to_pylist()), 'reference valid in every sample')
    ok(model.track_id == TRACK and model.lap_length_m == 4654.4,
       'track identity and simulator distance axis retained')
    ok(raw['reference_lap']['car_id'] == CAR, 'reference belongs to the P3 car')
    ok([c.id for c in model.corners] == [z[0] for z in ZONES],
       'all twelve curated corner IDs retained in order')
    for corner, (cid, name, short, geometry) in zip(raw['corners'], ZONES):
        meta = {k: v for k, v in corner.items()
                if k not in {'s_start_m', 'apex_s_m', 's_end_m'}}
        ok(meta == dict(id=cid, name=name, short_name=short, apex_side='right',
                        apex_side_source='default_cli_option'),
           f'{cid}: complete original non-geometry metadata retained')
        actual = tuple(corner[k] for k in ('s_start_m', 'apex_s_m', 's_end_m'))
        ok(actual == geometry, f'{cid}: reviewed geometry retained/refreshed')
    ok(all(a.s_end_m <= b.s_start_m for a, b in zip(model.corners, model.corners[1:])),
       'retained secondary corners do not overlap refreshed neighbours')
    ok(resolve_reference_lap('Circuit de Barcelona', vehicle_name=VEHICLE) == refs[0],
       'live coach resolves Barcelona/P3 reference')
    ok(resolve_track_model('Circuit de Barcelona', vehicle_name=VEHICLE) == MODEL,
       'live coach resolves Barcelona/P3 model')
    other = resolve_reference_lap('Circuit de Barcelona',
                                 vehicle_name='Ferrari AF Corse 2026 #50:LM')
    ok(other is not None and other != refs[0], 'Ferrari reference stays car-specific')
    if SESSION.exists():
        sys.path.insert(0, str(ROOT / 'dev/scripts'))
        from export_fastest_reference_laps import find_complete_laps, segment_covers_full_lap
        source = pq.read_table(SESSION)
        candidates = find_complete_laps(source)
        best = min(candidates, key=lambda c: c[1])
        ok([c[0] for c in candidates] == [1, 2, 3, 4, 5],
           'guarded scan accepts only complete laps 1 through 5')
        ok(best[0] == 4 and abs(best[1] - 96.040) < 0.0005,
           'fastest complete session candidate is lap 4, not the 91.518 s lap 6')
        start, end = best[2:]
        ok(table.equals(source.slice(start, end - start), check_metadata=False),
           'exported reference is the exact winning contiguous source slice')
        segments = build_segments(source['lap_number'].to_pylist())
        _, start6, end6 = segments[6]
        ok(not segment_covers_full_lap(source, start6, end6),
           'lap 6 is rejected despite valid flags: it stops at 4295 m')
    else:
        print('[SKIP] local qualifying recording unavailable; asset contracts still checked')


if __name__ == '__main__':
    main()
    print(f'{passed}/{passed + failed} assertions passed')
    sys.exit(bool(failed))
