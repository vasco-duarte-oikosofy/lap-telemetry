/**
 * Track coaching model generator tests.
 *
 * Run: node dev/scripts/test_generate_track_coaching_model_from_reference.js
 */
// @parallel true

'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const SCRIPT = path.join(ROOT, 'dev', 'scripts', 'generate_track_coaching_model_from_reference.py');
let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function runPython(code, args = []) {
  return spawnSync('python3', ['-c', code, ...args], {
    cwd: ROOT,
    encoding: 'utf8',
    timeout: 30000,
    env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product', 'python') },
  });
}

function writeSyntheticLap(file, dips, opts = {}) {
  const code = String.raw`
import sys
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

out = Path(sys.argv[1])
dips = [tuple(map(float, item.split(':'))) for item in sys.argv[2].split(',') if item]
include_car = sys.argv[3] == '1'
rows = 1200
lap_distance = [float(i) for i in range(rows)]
speed = []
for i in range(rows):
    v = 220.0
    for center, depth, width in dips:
        effect = max(0.0, 1.0 - abs(i - center) / width)
        v -= depth * effect
    speed.append(v)
fields = {
    'lap_distance_m': pa.array(lap_distance, pa.float32()),
    'speed_kph': pa.array(speed, pa.float32()),
    'lap_time_s': pa.array([i / 50.0 for i in range(rows)], pa.float32()),
    'lap_number': pa.array([1 for _ in range(rows)], pa.int32()),
}
if include_car:
    fields['vehicle_id'] = pa.array(['synthetic-car' for _ in range(rows)], pa.string())
pq.write_table(pa.table(fields), out)
`;
  const dipsArg = dips.map(d => d.join(':')).join(',');
  const res = runPython(code, [file, dipsArg, opts.includeCar ? '1' : '0']);
  if (res.status !== 0) throw new Error(res.stderr || res.stdout);
}

function runGenerator(args) {
  return spawnSync('python3', [SCRIPT, ...args], {
    cwd: ROOT,
    encoding: 'utf8',
    timeout: 30000,
    env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product', 'python') },
  });
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function runSyntheticTests(tmp) {
  const oneLap = path.join(tmp, 'one.parquet');
  const oneOut = path.join(tmp, 'one.json');
  writeSyntheticLap(oneLap, [[300, 80, 70]], { includeCar: true });
  let res = runGenerator(['--reference-lap', oneLap, '--track-id', 'synthetic', '--layout-id', 'test', '--out', oneOut]);
  assert(res.status === 0, 'single synthetic lap generation succeeds', res.stderr.trim());
  let model = readJson(oneOut);
  assert(model.corners.length === 1, 'single V-shaped trace produces one corner', String(model.corners.length));
  assert(Math.abs(model.corners[0].apex_s_m - 300) <= 2, 'single V-shaped trace apex is near expected distance', String(model.corners[0].apex_s_m));
  assert(model.reference_lap.car_id === 'synthetic-car', 'car id is read from vehicle_id column', model.reference_lap.car_id);

  const twoLap = path.join(tmp, 'two.parquet');
  const twoOut = path.join(tmp, 'two.json');
  writeSyntheticLap(twoLap, [[250, 75, 60], [700, 65, 60]], { includeCar: true });
  res = runGenerator(['--reference-lap', twoLap, '--track-id', 'synthetic', '--layout-id', 'test', '--out', twoOut]);
  assert(res.status === 0, 'two-corner synthetic lap generation succeeds', res.stderr.trim());
  model = readJson(twoOut);
  assert(model.corners.length === 2, 'two separated V-shaped traces produce two corners', String(model.corners.length));
  assert(model.corners[0].apex_s_m < model.corners[1].apex_s_m, 'generated corners are sorted by distance');

  const mergeLap = path.join(tmp, 'merge.parquet');
  const mergeOut = path.join(tmp, 'merge.json');
  writeSyntheticLap(mergeLap, [[300, 35, 25], [325, 80, 25]], { includeCar: true });
  res = runGenerator(['--reference-lap', mergeLap, '--track-id', 'synthetic', '--layout-id', 'test', '--out', mergeOut, '--min-separation-m', '60']);
  assert(res.status === 0, 'nearby synthetic minima generation succeeds', res.stderr.trim());
  model = readJson(mergeOut);
  assert(model.corners.length === 1, 'min-distance merging avoids duplicate apexes', String(model.corners.length));
  assert(Math.abs(model.corners[0].apex_s_m - 325) <= 3, 'min-distance merging keeps strongest nearby candidate', String(model.corners[0].apex_s_m));

  const missingCarLap = path.join(tmp, 'missing-car.parquet');
  const missingCarOut = path.join(tmp, 'missing-car.json');
  writeSyntheticLap(missingCarLap, [[300, 80, 70]], { includeCar: false });
  res = runGenerator(['--reference-lap', missingCarLap, '--track-id', 'synthetic', '--layout-id', 'test', '--out', missingCarOut]);
  assert(res.status !== 0 && res.stderr.includes('car identity'), 'missing car identity fails without --car-id', res.stderr.trim());
  res = runGenerator(['--reference-lap', missingCarLap, '--track-id', 'synthetic', '--layout-id', 'test', '--car-id', 'manual-car', '--out', missingCarOut]);
  assert(res.status === 0, 'missing car identity succeeds with --car-id', res.stderr.trim());
  model = readJson(missingCarOut);
  assert(model.reference_lap.car_id === 'manual-car', 'generated JSON includes manual car_id', model.reference_lap.car_id);
}

function runBarcelonaTest(tmp) {
  const referenceLap = path.join(ROOT, 'product', 'data', 'reference-laps', 'circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet');
  const out = path.join(tmp, 'barcelona.json');
  const diagnostics = path.join(tmp, 'barcelona.diagnostics.txt');
  const res = runGenerator([
    '--reference-lap', referenceLap,
    '--track-id', 'circuit-de-barcelona',
    '--layout-id', 'lmu-default',
    '--car-id', 'dkr-engineering-4-elms25',
    '--out', out,
    '--diagnostics-out', diagnostics,
  ]);
  assert(res.status === 0, 'Barcelona reference lap generation succeeds', res.stderr.trim());
  const model = readJson(out);
  assert(model.reference_lap.car_id === 'dkr-engineering-4-elms25', 'Barcelona output records reference car id', model.reference_lap.car_id);
  const sorted = model.corners.every((corner, index, corners) => index === 0 || corners[index - 1].s_end_m <= corner.s_start_m);
  assert(sorted, 'Barcelona corner zones are sorted and non-overlapping');
  const apexes = model.corners.map(c => c.apex_s_m);
  for (const expected of [829, 941, 1162, 1730]) {
    const nearest = apexes.reduce((best, value) => Math.abs(value - expected) < Math.abs(best - expected) ? value : best, apexes[0]);
    assert(Math.abs(nearest - expected) <= 20, `Barcelona candidate near ${expected}m`, `nearest=${nearest}`);
  }
  const diagnosticsText = fs.readFileSync(diagnostics, 'utf8');
  assert(diagnosticsText.includes('accepted'), 'Barcelona diagnostics include accepted candidates');
}

function main() {
  console.log('═══ Track Model From Reference Lap Tests ═══\n');
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'track-model-generator-'));
  try {
    runSyntheticTests(tmp);
    runBarcelonaTest(tmp);
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) process.exit(1);
}

main();
