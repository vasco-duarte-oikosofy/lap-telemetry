/**
 * Bug 16: slow/pitstop laps should be rejected before coaching/compare.
 * Run: node dev/scripts/test_bug16_slow_lap_guard.js
 */
// @parallel true

'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const PYTHONPATH = path.join(ROOT, 'product', 'python');

let pass = 0;
let fail = 0;
function ok(condition, label, detail = '') {
  if (condition) { pass++; console.log(`  [PASS] ${label}${detail ? ' — ' + detail : ''}`); }
  else { fail++; console.log(`  [FAIL] ${label}${detail ? ' — ' + detail : ''}`); }
}

function runPythonTests() {
  const code = String.raw`
from pathlib import Path
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

from lap_telemetry.coach.facts import PartialLapError
from lap_telemetry.coach.lap_comparator import compare_laps
from lap_telemetry.coach.track_model import TrackCoachingModel, load_track_coaching_model

ROOT = Path(r'''${ROOT}''')
BUG_DIRS = [
    ROOT / 'work/active/bugs/16-slow-pitstop-lap-passes-guard',
    ROOT / 'work/completed/bugs/16-slow-pitstop-lap-passes-guard',
]
BUG_DIR = next((p for p in BUG_DIRS if p.exists()), BUG_DIRS[0])
SESSION = BUG_DIR / 'session_20260529T143959Z_bahrain-outer-circuit_lmu.parquet'
REF = BUG_DIR / 'bahrain-outer-circuit_dkr-engineering-4-elms25_time_01.11.380.parquet'
MODEL = BUG_DIR / 'bahrain-outer-circuit_dkr-engineering-4-elms25.json'

if SESSION.exists() and REF.exists() and MODEL.exists():
    model = load_track_coaching_model(MODEL)
    try:
        compare_laps(SESSION, REF, model, lap_number=13)
        raise AssertionError('lap 13 should have been rejected as slow/pitstop')
    except PartialLapError as exc:
        msg = str(exc).lower()
        assert 'duration' in msg or 'pitstop' in msg or 'safety-car' in msg, msg


def make_lap(path, lap_number, duration, scorer_in_same_segment=False):
    rows = []
    scorer = duration if scorer_in_same_segment else None
    for d, lt in [(0.0, 0.0), (500.0, duration / 2), (1000.0, duration)]:
        rows.append({
            'lap_number': lap_number,
            'lap_distance_m': d,
            'lap_time_s': lt,
            'speed_kph': 180.0,
            'throttle_norm': 1.0,
            'brake_norm': 0.0,
            'scoring_last_lap_time_s': scorer,
        })
    pq.write_table(pa.table({k: pa.array([r[k] for r in rows]) for k in rows[0]}), path)


def make_session(path, lap_duration, next_scorer=None):
    rows = []
    for d, lt in [(0.0, 0.0), (500.0, lap_duration / 2), (1000.0, lap_duration)]:
        rows.append({
            'lap_number': 5,
            'lap_distance_m': d,
            'lap_time_s': lt,
            'speed_kph': 180.0,
            'throttle_norm': 1.0,
            'brake_norm': 0.0,
            'scoring_last_lap_time_s': None,
        })
    # Next segment carries lap 5 scorer duration. If absent, the helper falls back to max(lap_time_s).
    scorer = next_scorer if next_scorer is not None else lap_duration
    for d, lt in [(0.0, 0.0), (500.0, 10.0), (1000.0, 20.0)]:
        rows.append({
            'lap_number': 6,
            'lap_distance_m': d,
            'lap_time_s': lt,
            'speed_kph': 180.0,
            'throttle_norm': 1.0,
            'brake_norm': 0.0,
            'scoring_last_lap_time_s': scorer,
        })
    pq.write_table(pa.table({k: pa.array([r[k] for r in rows]) for k in rows[0]}), path)

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    ref = td / 'ref.parquet'
    session = td / 'session.parquet'
    model = TrackCoachingModel('1', 'test', 'test', 1000.0, [], [])
    make_lap(ref, 1, 100.0, scorer_in_same_segment=True)

    make_session(session, 115.0, next_scorer=115.0)
    facts = compare_laps(session, ref, model, lap_number=5)
    assert abs(facts.lap_time_delta_s - 15.0) < 1e-9, facts.lap_time_delta_s

    make_session(session, 115.0, next_scorer=120.0)
    facts = compare_laps(session, ref, model, lap_number=5)
    assert abs(facts.lap_time_delta_s - 15.0) < 1e-9, facts.lap_time_delta_s

    make_session(session, 116.0, next_scorer=116.0)
    try:
        compare_laps(session, ref, model, lap_number=5)
        raise AssertionError('116% lap should be rejected')
    except PartialLapError as exc:
        assert 'duration' in str(exc).lower(), exc

print('python bug16 checks OK')
`;
  return spawnSync('python3', ['-c', code], {
    encoding: 'utf8',
    timeout: 60000,
    env: { ...process.env, PYTHONPATH },
  });
}

async function runJsTests() {
  const source = fs.readFileSync(path.join(ROOT, 'product', 'web', 'js', 'pipeline.js'), 'utf8');
  const mod = await import(`data:text/javascript;charset=utf-8,${encodeURIComponent(source)}`);
  ok(mod.isSlowLapComparedToReference({ duration: 116 }, { duration: 100 }) === true,
    'JS rejects laps over slow-lap ratio');
  ok(mod.isSlowLapComparedToReference({ duration: 115 }, { duration: 100 }) === false,
    'JS allows laps exactly at slow-lap ratio');
  ok(mod.isSlowLapComparedToReference({ duration: 0 }, { duration: 100 }) === false,
    'JS ignores missing driver duration');
  ok(mod.isSlowLapComparedToReference({ duration: 116 }, { duration: 0 }) === false,
    'JS ignores missing reference duration');

  const segments = [
    { lapNum: 1, start: 0, end: 3 },
    { lapNum: 2, start: 3, end: 6 },
    { lapNum: 3, start: 6, end: 9 },
  ];
  const dist = [0, 500, 1000, 0, 500, 1000, 0, 500, 1000];
  const lapTimes = [0, 50, 100, 0, 58, 116, 0, 50, 100];
  mod.annotateSegments(segments, dist, lapTimes);
  ok(segments[1].partial === true, 'JS annotateSegments flags slow full-distance lap partial');
}

async function main() {
  console.log('═══ Bug 16 slow lap guard tests ═══\n');
  const res = runPythonTests();
  process.stdout.write(res.stdout || '');
  process.stderr.write(res.stderr || '');
  ok(!res.error, 'python bug16 tests spawned', res.error?.message || '');
  ok(res.status === 0, 'python bug16 tests exited 0', res.status === 0 ? '' : `status ${res.status}`);
  try {
    await runJsTests();
  } catch (err) {
    ok(false, 'JS bug16 tests completed', err.stack || err.message);
  }
  const total = pass + fail;
  console.log(`\n  ${pass}/${total} assertions passed`);
  if (fail > 0) process.exit(1);
}

main();
