/**
 * Track outline/apex Phase 04.2 apex surface/terrain tests.
 *
 * Run: node scripts/test_apex_metrics_surface_terrain.js
 */
// @parallel true

'use strict';

const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function corner(overrides = {}) {
  return {
    id: 't1',
    name: 'Turn 1',
    s_start_m: 90,
    s_end_m: 120,
    apex_s_m: 105,
    apex_side: 'right',
    ...overrides,
  };
}

function lapData(overrides = {}) {
  return {
    lap_number: [1, 1, 1],
    raw_lap_distance_m: [98, 106, 118],
    distance_to_track_edge_m: [8, 3.5, 7],
    path_lateral_m: [1, 2, 1],
    track_edge_m: [9, 5.5, 8],
    surface_type_fl: [10, 11, 12],
    surface_type_fr: [20, 21, 22],
    surface_type_rl: [30, 31, 32],
    surface_type_rr: [40, 41, 42],
    terrain_name_fl: ['fl0', 'left-front-kerb', 'fl2'],
    terrain_name_fr: ['fr0', 'right-front-kerb', 'fr2'],
    terrain_name_rl: ['rl0', 'left-rear-grass', 'rl2'],
    terrain_name_rr: ['rr0', 'right-rear-gravel', 'rr2'],
    ...overrides,
  };
}

async function runTests() {
  const mod = await import(path.join(ROOT, 'product/web/js/apexMetrics.js'));

  const right = mod.computeApexMetricForLap(lapData(), corner({ apex_side: 'right' }));
  assert(right.surface_type === 21 && right.terrain_name === 'right-front-kerb',
    'right apex reports front-right surface and terrain', JSON.stringify(right));

  const left = mod.computeApexMetricForLap(lapData(), corner({ apex_side: 'left' }));
  assert(left.surface_type === 11 && left.terrain_name === 'left-front-kerb',
    'left apex reports front-left surface and terrain', JSON.stringify(left));

  const rightFallback = mod.computeApexMetricForLap(
    lapData({ surface_type_fr: [20, null, 22], terrain_name_fr: ['fr0', null, 'fr2'] }),
    corner({ apex_side: 'right' })
  );
  assert(rightFallback.surface_type === 41 && rightFallback.terrain_name === 'right-rear-gravel',
    'missing right-front values fall back to right-rear values', JSON.stringify(rightFallback));

  const leftMissing = mod.computeApexMetricForLap(
    lapData({
      surface_type_fl: [10, null, 12],
      surface_type_rl: [30, null, 32],
      terrain_name_fl: ['fl0', null, 'fl2'],
      terrain_name_rl: ['rl0', null, 'rl2'],
    }),
    corner({ apex_side: 'left' })
  );
  assert(leftMissing.surface_type === null && leftMissing.terrain_name === null,
    'missing apex-side wheel data returns null surface and terrain', JSON.stringify(leftMissing));
  assert(leftMissing.apex_distance_m === 3.5 && leftMissing.apex_timing_error_m === 1 && leftMissing.sample_s_m === 106,
    'missing side data does not change distance or timing metrics', JSON.stringify(leftMissing));
}

async function main() {
  console.log('═══ Track Outline Phase 04.2 Apex Surface/Terrain Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
