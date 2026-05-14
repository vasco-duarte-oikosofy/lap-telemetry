/**
 * Track outline/apex Phase 04 one-corner apex metric tests.
 *
 * Run: node scripts/test_apex_metrics.js
 */

'use strict';

const path = require('path');

const ROOT = path.resolve(__dirname, '..');
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
    name: 'La Source',
    s_start_m: 200,
    s_end_m: 360,
    apex_s_m: 285,
    apex_side: 'right',
    ...overrides,
  };
}

function lapData(overrides = {}) {
  return {
    lap_number: [7, 7, 7, 7],
    raw_lap_distance_m: [250, 281, 288, 370],
    distance_to_track_edge_m: [6.2, 4.5, 3.25, 1.0],
    path_lateral_m: [1.0, 2.0, -3.0, 4.0],
    track_edge_m: [7.2, 6.5, 6.25, 5.0],
    ...overrides,
  };
}

function isNullMetric(metric) {
  return metric.apex_distance_m === null &&
    metric.apex_timing_error_m === null &&
    metric.surface_type === null &&
    metric.terrain_name === null &&
    metric.sample_s_m === null;
}

async function runTests() {
  const mod = await import(path.join(ROOT, 'web/js/apexMetrics.js'));

  const metric = mod.computeApexMetricForLap(lapData(), corner());
  assert(metric.corner_id === 't1' && metric.corner_name === 'La Source' && metric.lap === 7,
    'metric includes corner identity and inferred lap label', JSON.stringify(metric));
  assert(metric.sample_s_m === 288, 'closest sample to apex_s_m is selected', String(metric.sample_s_m));
  assert(metric.apex_timing_error_m === 3, 'late apex timing error is positive', String(metric.apex_timing_error_m));
  assert(metric.apex_distance_m === 3.25, 'inside-edge distance uses selected sample value', String(metric.apex_distance_m));
  assert(metric.surface_type === null && metric.terrain_name === null, 'surface and terrain remain null in Phase 04');

  const early = mod.computeApexMetricForLap(
    lapData({ raw_lap_distance_m: [250, 279, 281, 370], distance_to_track_edge_m: [6.2, 4.5, 3.25, 1.0] }),
    corner()
  );
  assert(early.sample_s_m === 281 && early.apex_timing_error_m === -4,
    'early apex timing error is negative', JSON.stringify(early));

  const derived = mod.computeApexMetricForLap(
    lapData({ distance_to_track_edge_m: [] }),
    corner()
  );
  assert(derived.sample_s_m === 288 && derived.apex_distance_m === 3.25,
    'inside-edge distance derives from track_edge_m - abs(path_lateral_m) at selected sample', JSON.stringify(derived));

  const missingRaw = mod.computeApexMetricForLap(
    lapData({ raw_lap_distance_m: undefined, lap_distance_m: [250, 281, 288, 370] }),
    corner()
  );
  assert(isNullMetric(missingRaw), 'missing raw_lap_distance_m returns null metric fields without lap_distance fallback', JSON.stringify(missingRaw));

  const missingDistance = mod.computeApexMetricForLap(
    lapData({ distance_to_track_edge_m: [], path_lateral_m: undefined, track_edge_m: undefined }),
    corner()
  );
  assert(isNullMetric(missingDistance), 'missing edge-distance inputs return null metric fields without throwing', JSON.stringify(missingDistance));

  const noSamples = mod.computeApexMetricForLap(
    lapData({ raw_lap_distance_m: [100, 120, 380, 390] }),
    corner()
  );
  assert(isNullMetric(noSamples), 'no samples inside corner window returns null metric fields', JSON.stringify(noSamples));
}

async function main() {
  console.log('═══ Track Outline Phase 04 Apex Metric Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
