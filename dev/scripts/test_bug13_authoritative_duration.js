/**
 * Bug 13: authoritative lap duration should use scorer last-lap time when available.
 * Run: node dev/scripts/test_bug13_authoritative_duration.js
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
import contextlib
import io
import json
import math
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from lap_telemetry.parquet_utils import authoritative_duration, build_segments
from lap_telemetry import summary
from lap_telemetry.coach.lap_comparator import compare_laps
from lap_telemetry.coach.track_model import TrackCoachingModel


def table(rows):
    cols = {k: pa.array([r.get(k) for r in rows]) for k in rows[0].keys()}
    return pa.table(cols)


def write_table(t, path):
    pq.write_table(t, path)


rows = []
# Lap 5 raw max is 71.952; scorer arrives in next segment as 72.029.
for d, lt in [(0.0, 0.0), (500.0, 20.0), (1000.0, 71.952)]:
    rows.append({
        'lap_number': 5, 'lap_distance_m': d, 'lap_time_s': lt,
        'speed_kph': 180.0, 'throttle_norm': 1.0, 'brake_norm': 0.0,
        'scoring_last_lap_time_s': 70.000,
    })
# Lap 6 raw max is 71.724; first rows carry lap 5's authoritative duration.
for d, lt, last in [(0.0, 0.0, 72.029), (500.0, 20.0, 72.029), (1000.0, 71.724, 72.029)]:
    rows.append({
        'lap_number': 6, 'lap_distance_m': d, 'lap_time_s': lt,
        'speed_kph': 180.0, 'throttle_norm': 1.0, 'brake_norm': 0.0,
        'scoring_last_lap_time_s': last,
    })
# Lap 7 first rows carry lap 6's authoritative duration.
for d, lt, last in [(0.0, 0.0, 71.900), (500.0, 20.0, 71.900), (1000.0, 72.500, 71.900)]:
    rows.append({
        'lap_number': 7, 'lap_distance_m': d, 'lap_time_s': lt,
        'speed_kph': 180.0, 'throttle_norm': 1.0, 'brake_norm': 0.0,
        'scoring_last_lap_time_s': last,
    })

t = table(rows)
segments = build_segments(t.column('lap_number').to_pylist())

lap5 = authoritative_duration(t, segments[0][1], segments[0][2], segments[1][1], segments[1][2])
assert abs(lap5 - 72.029) < 1e-9, lap5

single_ref = table([
    {'lap_number': 6, 'lap_distance_m': 0.0, 'lap_time_s': 0.0, 'speed_kph': 180.0, 'throttle_norm': 1.0, 'brake_norm': 0.0, 'scoring_last_lap_time_s': 71.900},
    {'lap_number': 6, 'lap_distance_m': 500.0, 'lap_time_s': 20.0, 'speed_kph': 180.0, 'throttle_norm': 1.0, 'brake_norm': 0.0, 'scoring_last_lap_time_s': 71.900},
    {'lap_number': 6, 'lap_distance_m': 1000.0, 'lap_time_s': 71.724, 'speed_kph': 180.0, 'throttle_norm': 1.0, 'brake_norm': 0.0, 'scoring_last_lap_time_s': 71.900},
])
ref_auth = authoritative_duration(single_ref, 0, single_ref.num_rows, allow_same_segment_scoring=True)
assert abs(ref_auth - 71.900) < 1e-9, ref_auth

ref_no_same = authoritative_duration(single_ref, 0, single_ref.num_rows, allow_same_segment_scoring=False)
assert abs(ref_no_same - 71.724) < 1e-9, ref_no_same

invalid_table = table([
    {'lap_number': 1, 'lap_distance_m': 0.0, 'lap_time_s': 0.0, 'speed_kph': 180.0, 'throttle_norm': 1.0, 'brake_norm': 0.0, 'scoring_last_lap_time_s': 70.000},
    {'lap_number': 1, 'lap_distance_m': 1000.0, 'lap_time_s': 78.883, 'speed_kph': 180.0, 'throttle_norm': 1.0, 'brake_norm': 0.0, 'scoring_last_lap_time_s': 70.000},
    {'lap_number': 2, 'lap_distance_m': 0.0, 'lap_time_s': 0.0, 'speed_kph': 180.0, 'throttle_norm': 1.0, 'brake_norm': 0.0, 'scoring_last_lap_time_s': 71.679},
])
invalid = authoritative_duration(invalid_table, 0, 2, 2, 3)
assert abs(invalid - 78.883) < 1e-9, invalid

legacy = t.drop(['scoring_last_lap_time_s'])
legacy_dur = authoritative_duration(legacy, segments[0][1], segments[0][2], segments[1][1], segments[1][2])
assert abs(legacy_dur - 71.952) < 1e-9, legacy_dur

with tempfile.TemporaryDirectory() as td:
    session_path = Path(td) / 'session.parquet'
    ref_path = Path(td) / 'ref.parquet'
    write_table(t, session_path)
    write_table(single_ref, ref_path)

    model = TrackCoachingModel(
        schema_version='1', track_id='test', layout_id='test', lap_length_m=1000.0,
        corners=[], straight_zones=[])
    facts = compare_laps(session_path, ref_path, model, lap_number=5)
    assert abs(facts.lap_time_delta_s - (72.029 - 71.900)) < 1e-9, facts.lap_time_delta_s

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = summary.run(session_path)
    out = buf.getvalue()
    assert rc == 0
    assert '1:12.029' in out, out
    assert '1:11.900' in out, out

print('python bug13 checks OK')
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
  const segments = [
    { lapNum: 5, start: 0, end: 3 },
    { lapNum: 6, start: 3, end: 6 },
    { lapNum: 7, start: 6, end: 9 },
  ];
  const dist = [0, 500, 1000, 0, 500, 1000, 0, 500, 1000];
  const lapTimes = [0, 20, 71.952, 0, 20, 71.724, 0, 20, 72.500];
  const scoring = [70, 70, 70, 72.029, 72.029, 72.029, 71.900, 71.900, 71.900];
  mod.annotateSegments(segments, dist, lapTimes, scoring);
  ok(Math.abs(segments[0].duration - 72.029) < 1e-9, 'JS lap 5 duration uses next-segment scorer', `${segments[0].duration}`);
  ok(Math.abs(segments[1].duration - 71.900) < 1e-9, 'JS lap 6 duration uses next-segment scorer', `${segments[1].duration}`);
  ok(Math.abs(segments[2].duration - 72.500) < 1e-9, 'JS final segment falls back to lap_time_s', `${segments[2].duration}`);
  ok(segments[1].fastest === true, 'JS fastest flag uses corrected duration');

  const legacySegments = [
    { lapNum: 5, start: 0, end: 3 },
    { lapNum: 6, start: 3, end: 6 },
  ];
  mod.annotateSegments(legacySegments, dist.slice(0, 6), lapTimes.slice(0, 6));
  ok(Math.abs(legacySegments[0].duration - 71.952) < 1e-9, 'JS legacy files fall back to max lap_time_s');
}

async function main() {
  console.log('═══ Bug 13 authoritative duration tests ═══\n');
  const res = runPythonTests();
  process.stdout.write(res.stdout || '');
  process.stderr.write(res.stderr || '');
  ok(!res.error, 'python bug13 tests spawned', res.error?.message || '');
  ok(res.status === 0, 'python bug13 tests exited 0', res.status === 0 ? '' : `status ${res.status}`);

  try {
    await runJsTests();
  } catch (err) {
    ok(false, 'JS bug13 tests completed', err.stack || err.message);
  }

  const total = pass + fail;
  console.log(`\n  ${pass}/${total} assertions passed`);
  if (fail > 0) process.exit(1);
}

main();
