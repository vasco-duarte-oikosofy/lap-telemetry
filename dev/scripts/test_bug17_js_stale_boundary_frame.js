/**
 * Bug 17: stale start-boundary frames must not make partial laps look complete.
 * Run: node dev/scripts/test_bug17_js_stale_boundary_frame.js
 */
// @parallel true

'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const REPRO = path.join(
  ROOT,
  'work',
  'completed',
  'bugs',
  '16-slow-pitstop-lap-passes-guard',
  'session_20260529T143959Z_bahrain-outer-circuit_lmu.parquet'
);

let pass = 0;
let fail = 0;
function ok(condition, label, detail = '') {
  if (condition) { pass++; console.log(`  [PASS] ${label}${detail ? ' — ' + detail : ''}`); }
  else { fail++; console.log(`  [FAIL] ${label}${detail ? ' — ' + detail : ''}`); }
}

async function loadPipeline() {
  const source = fs.readFileSync(path.join(ROOT, 'product', 'web', 'js', 'pipeline.js'), 'utf8');
  return import(`data:text/javascript;charset=utf-8,${encodeURIComponent(source)}`);
}

function syntheticStaleBoundaryCase(mod) {
  const segments = [
    { lapNum: 18, start: 0, end: 4 },
    { lapNum: 19, start: 4, end: 10 },
  ];
  const distances = [
    0, 1000, 2400, 3500,
    3509, 3513, 3, 600, 1600, 2416,
  ];
  const lapTimes = [
    0, 20, 50, 71,
    -0.115, -0.095, 0.085, 12, 32, 51.085,
  ];
  mod.annotateSegments(segments, distances, lapTimes);
  const partialLap = segments[1];
  ok(partialLap.maxDist < 2500, 'synthetic stale boundary frames ignored for maxDist', `maxDist=${partialLap.maxDist}`);
  ok(partialLap.partial === true, 'synthetic stale-boundary lap is partial');
  ok(partialLap.fastest === false, 'synthetic stale-boundary lap is not fastest');
}

function loadRealLaps() {
  const code = String.raw`
import json
from pathlib import Path
import pyarrow.parquet as pq

path = Path(r'''${REPRO}''')
table = pq.ParquetFile(path).read(columns=['lap_number', 'lap_distance_m', 'lap_time_s', 'scoring_last_lap_time_s'])
cols = {name: table[name].to_pylist() for name in table.column_names}
keep = [i for i, lap in enumerate(cols['lap_number']) if lap in (18, 19)]
print(json.dumps({name: [cols[name][i] for i in keep] for name in cols}))
`;
  return spawnSync('python3', ['-c', code], {
    encoding: 'utf8',
    timeout: 60000,
    env: { ...process.env },
    maxBuffer: 20 * 1024 * 1024,
  });
}

function realReproCase(mod) {
  const res = loadRealLaps();
  process.stderr.write(res.stderr || '');
  ok(!res.error, 'real repro extractor spawned', res.error?.message || '');
  ok(res.status === 0, 'real repro extractor exited 0', res.status === 0 ? '' : `status ${res.status}`);
  if (res.error || res.status !== 0) return;

  const data = JSON.parse(res.stdout);
  const segments = mod.buildSegments(data.lap_number);
  mod.annotateSegments(segments, data.lap_distance_m, data.lap_time_s, data.scoring_last_lap_time_s);
  const lap18 = segments.find(s => s.lapNum === 18);
  const lap19 = segments.find(s => s.lapNum === 19);
  ok(Boolean(lap18), 'real repro lap 18 segment exists');
  ok(Boolean(lap19), 'real repro lap 19 segment exists');
  if (!lap18 || !lap19) return;

  ok(lap18.partial === false, 'real repro lap 18 remains clean', `maxDist=${lap18.maxDist}, duration=${lap18.duration}`);
  ok(lap19.maxDist > 2350 && lap19.maxDist < 2500,
    'real repro lap 19 maxDist reflects useful partial data', `maxDist=${lap19.maxDist}`);
  ok(lap19.partial === true, 'real repro lap 19 is partial');
  ok(lap19.fastest === false, 'real repro lap 19 is not fastest');
}

async function main() {
  console.log('═══ Bug 17 JS stale boundary frame tests ═══\n');
  try {
    const mod = await loadPipeline();
    syntheticStaleBoundaryCase(mod);
    realReproCase(mod);
  } catch (err) {
    ok(false, 'bug17 tests completed', err.stack || err.message);
  }
  const total = pass + fail;
  console.log(`\n  ${pass}/${total} assertions passed`);
  if (fail > 0) process.exit(1);
}

main();
