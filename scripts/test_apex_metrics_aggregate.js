/**
 * Track outline/apex Phase 04.1 all-laps/all-corners metric tests.
 *
 * Run: node scripts/test_apex_metrics_aggregate.js
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

function annotations() {
  return {
    track_id: 'synthetic-track',
    layout_id: 'default',
    corners: [
      { id: 't1', name: 'Turn 1', s_start_m: 90, s_end_m: 115, apex_s_m: 105, apex_side: 'right' },
      { id: 't2', name: 'Turn 2', s_start_m: 190, s_end_m: 215, apex_s_m: 205, apex_side: 'left' },
    ],
  };
}

function sessionEntry(overrides = {}) {
  return {
    data: {
      lap_number: [1, 1, 1, 1, 2, 2, 2, 2],
      raw_lap_distance_m: [98, 108, 198, 204, 95, 103, 197, 209],
      distance_to_track_edge_m: [9, 4, 8, 2, 7, 3, 6, 1.5],
      path_lateral_m: [1, 1, 1, 1, 1, 1, 1, 1],
      track_edge_m: [10, 5, 9, 3, 8, 4, 7, 2.5],
      ...overrides.data,
    },
    segments: overrides.segments || [
      { lapNum: 1, start: 0, end: 4 },
      { lapNum: 2, start: 4, end: 8 },
    ],
  };
}

function metricKey(metric) {
  return `${metric.lap}:${metric.corner_id}`;
}

async function runTests() {
  const mod = await import(path.join(ROOT, 'web/js/apexMetrics.js'));

  const result = mod.computeApexMetricsForSession(sessionEntry(), { status: 'ok', annotations: annotations() });
  assert(result.status === 'ok', 'aggregator returns ok for configured compatible telemetry', JSON.stringify(result));
  assert(result.metrics.length === 4, 'aggregator returns one metric per lap/corner pair', String(result.metrics.length));
  assert(result.metrics.map(metricKey).join('|') === '1:t1|1:t2|2:t1|2:t2',
    'aggregator ordering is lap order then annotation corner order', result.metrics.map(metricKey).join('|'));
  assert(result.metrics.map(m => m.sample_s_m).join('|') === '108|204|103|209',
    'aggregator calls one-corner helper for each selected lap sample', result.metrics.map(m => m.sample_s_m).join('|'));
  assert(result.metrics.map(m => m.apex_timing_error_m).join('|') === '3|-1|-2|4',
    'aggregator preserves early/late timing per metric', result.metrics.map(m => m.apex_timing_error_m).join('|'));

  const directAnnotations = mod.computeApexMetricsForSession(sessionEntry(), annotations());
  assert(directAnnotations.status === 'ok' && directAnnotations.metrics.length === 4,
    'aggregator accepts validated annotation objects directly', JSON.stringify(directAnnotations));

  const notConfigured = mod.computeApexMetricsForSession(sessionEntry(), { status: 'not_configured', annotations: null });
  assert(notConfigured.status === 'not_configured' && Array.isArray(notConfigured.metrics) && notConfigured.metrics.length === 0,
    'not configured annotations return empty not_configured result', JSON.stringify(notConfigured));

  const legacy = mod.computeApexMetricsForSession(
    sessionEntry({ data: { raw_lap_distance_m: [], lap_distance_m: [98, 108, 198, 204, 95, 103, 197, 209] } }),
    { status: 'ok', annotations: annotations() }
  );
  assert(legacy.status === 'unavailable' && legacy.metrics.length === 0 && legacy.reason.includes('raw_lap_distance_m'),
    'legacy telemetry returns empty unavailable result without lap_distance fallback', JSON.stringify(legacy));

  const missingDistance = mod.computeApexMetricsForSession(
    sessionEntry({ data: { distance_to_track_edge_m: [], path_lateral_m: [], track_edge_m: [] } }),
    { status: 'ok', annotations: annotations() }
  );
  assert(missingDistance.status === 'unavailable' && missingDistance.metrics.length === 0 && missingDistance.reason.includes('edge distance'),
    'telemetry without edge-distance inputs returns empty unavailable result', JSON.stringify(missingDistance));
}

async function main() {
  console.log('═══ Track Outline Phase 04.1 Apex Metric Aggregator Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
