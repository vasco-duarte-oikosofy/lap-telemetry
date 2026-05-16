/**
 * Track outline/apex Phase 06 optional apex metrics sidecar export tests.
 *
 * Run: node scripts/test_apex_metrics_export.js
 */
// @parallel true

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..', '..');
const EXPORT_SCRIPT = path.join(ROOT, 'dev/scripts/export_apex_metrics.js');

let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function tempPath(name, ext) {
  return path.join(os.tmpdir(), `${name}-${Date.now()}-${Math.random().toString(16).slice(2)}${ext}`);
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2));
}

function buildParquet({ name, outlineColumns }) {
  const out = tempPath(name, '.parquet');
  const code = `
import pyarrow as pa, pyarrow.parquet as pq
lap_number = [1, 1, 1, 1, 2, 2, 2, 2]
lap_time_s = [0.1, 1.0, 2.0, 3.0, 0.1, 1.0, 2.0, 3.0]
lap_distance_m = [98.0, 108.0, 198.0, 204.0, 95.0, 103.0, 197.0, 209.0]
cols = [
  pa.array(lap_number, type=pa.int32()),
  pa.array(lap_time_s, type=pa.float32()),
  pa.array(lap_distance_m, type=pa.float32()),
]
names = ['lap_number', 'lap_time_s', 'lap_distance_m']
if ${outlineColumns ? 'True' : 'False'}:
  cols.extend([
    pa.array([98.0, 108.0, 198.0, 204.0, 95.0, 103.0, 197.0, 209.0], type=pa.float32()),
    pa.array([1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0], type=pa.float32()),
    pa.array([10.0, 5.0, 9.0, 3.0, 8.0, 4.0, 7.0, 2.5], type=pa.float32()),
    pa.array([9.0, 4.0, 8.0, 2.0, 7.0, 3.0, 6.0, 1.5], type=pa.float32()),
    pa.array([10, 11, 12, 13, 14, 15, 16, 17], type=pa.int32()),
    pa.array([20, 21, 22, 23, 24, 25, 26, 27], type=pa.int32()),
    pa.array([30, 31, 32, 33, 34, 35, 36, 37], type=pa.int32()),
    pa.array([40, 41, 42, 43, 44, 45, 46, 47], type=pa.int32()),
    pa.array(['lf0', 'lf1', 'lf2', 'left-front-l1', 'lf4', 'lf5', 'lf6', 'left-front-l2'], type=pa.string()),
    pa.array(['rf0', 'right-front-l1', 'rf2', 'rf3', 'rf4', 'right-front-l2', 'rf6', 'rf7'], type=pa.string()),
    pa.array(['lr0', 'lr1', 'lr2', 'lr3', 'lr4', 'lr5', 'lr6', 'lr7'], type=pa.string()),
    pa.array(['rr0', 'rr1', 'rr2', 'rr3', 'rr4', 'rr5', 'rr6', 'rr7'], type=pa.string()),
  ])
  names.extend([
    'raw_lap_distance_m', 'path_lateral_m', 'track_edge_m',
    'distance_to_track_edge_m', 'surface_type_fl', 'surface_type_fr',
    'surface_type_rl', 'surface_type_rr', 'terrain_name_fl',
    'terrain_name_fr', 'terrain_name_rl', 'terrain_name_rr',
  ])
pq.write_table(pa.Table.from_arrays(cols, names=names), r'''${out}''', compression='snappy')
`;
  const res = spawnSync('python3', ['-c', code], { encoding: 'utf8', timeout: 30000 });
  if (res.error || res.status !== 0) throw new Error(res.error?.message || res.stderr);
  return out;
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

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

async function runTests() {
  const { exportApexMetricsSidecar } = require(EXPORT_SCRIPT);

  const sessionPath = buildParquet({ name: 'apex-export-configured', outlineColumns: true });
  const annotationsPath = tempPath('apex-export-annotations', '.json');
  const outPath = tempPath('apex-export-metrics', '.json');
  writeJson(annotationsPath, annotations());

  const exported = await exportApexMetricsSidecar({ sessionPath, annotationsPath, outPath });
  const disk = readJson(outPath);
  const expectedMetrics = [
    { corner_id: 't1', corner_name: 'Turn 1', lap: 1, apex_distance_m: 4, apex_timing_error_m: 3, surface_type: 21, terrain_name: 'right-front-l1', sample_s_m: 108 },
    { corner_id: 't2', corner_name: 'Turn 2', lap: 1, apex_distance_m: 2, apex_timing_error_m: -1, surface_type: 13, terrain_name: 'left-front-l1', sample_s_m: 204 },
    { corner_id: 't1', corner_name: 'Turn 1', lap: 2, apex_distance_m: 3, apex_timing_error_m: -2, surface_type: 25, terrain_name: 'right-front-l2', sample_s_m: 103 },
    { corner_id: 't2', corner_name: 'Turn 2', lap: 2, apex_distance_m: 1.5, apex_timing_error_m: 4, surface_type: 17, terrain_name: 'left-front-l2', sample_s_m: 209 },
  ];
  assert(exported.status === 'ok' && disk.status === 'ok', 'configured fixture exports ok sidecar', JSON.stringify(disk));
  assert(disk.schema_version === 1, 'sidecar schema_version is deterministic', String(disk.schema_version));
  assert(disk.source_session === sessionPath, 'sidecar identifies source session', disk.source_session);
  assert(disk.source_annotations === annotationsPath, 'sidecar identifies source annotations', disk.source_annotations);
  assert(disk.annotation_track_id === 'synthetic-track' && disk.annotation_layout_id === 'default',
    'sidecar includes annotation track/layout ids', JSON.stringify(disk));
  assert(JSON.stringify(disk.metrics) === JSON.stringify(expectedMetrics),
    'configured fixture writes expected §0.3 metrics in lap/corner order', JSON.stringify(disk.metrics));

  const cliOut = tempPath('apex-export-cli-metrics', '.json');
  const cli = spawnSync('node', [EXPORT_SCRIPT, '--session', sessionPath, '--annotations', annotationsPath, '--out', cliOut], {
    encoding: 'utf8',
    timeout: 30000,
  });
  assert(cli.status === 0 && readJson(cliOut).status === 'ok',
    'CLI command writes configured sidecar on demand', `${cli.stdout}${cli.stderr}`.trim());

  const invalidAnnotationsPath = tempPath('apex-export-invalid-annotations', '.json');
  const invalidOut = tempPath('apex-export-invalid-metrics', '.json');
  fs.writeFileSync(invalidAnnotationsPath, '{not valid json');
  const invalidCli = spawnSync('node', [EXPORT_SCRIPT, '--session', sessionPath, '--annotations', invalidAnnotationsPath, '--out', invalidOut], {
    encoding: 'utf8',
    timeout: 30000,
  });
  assert(invalidCli.status !== 0 && invalidCli.stderr.includes('invalid annotations') && !fs.existsSync(invalidOut),
    'CLI returns non-zero useful error for invalid annotations', invalidCli.stderr.trim());

  const sentinelOut = tempPath('apex-export-sentinel', '.json');
  fs.writeFileSync(sentinelOut, 'SENTINEL');
  let refused = false;
  try {
    await exportApexMetricsSidecar({ sessionPath, annotationsPath, outPath: sentinelOut });
  } catch (err) {
    refused = err.message.includes('exists');
  }
  assert(refused, 'existing output file is refused by default');
  assert(fs.readFileSync(sentinelOut, 'utf8') === 'SENTINEL', 'refused export does not overwrite sentinel output');

  await exportApexMetricsSidecar({ sessionPath, annotationsPath, outPath: sentinelOut, overwrite: true });
  assert(readJson(sentinelOut).status === 'ok', 'explicit overwrite replaces existing output file');

  const legacyPath = buildParquet({ name: 'apex-export-legacy', outlineColumns: false });
  const legacyOut = tempPath('apex-export-legacy-metrics', '.json');
  const legacy = await exportApexMetricsSidecar({ sessionPath: legacyPath, annotationsPath, outPath: legacyOut });
  const legacyDisk = readJson(legacyOut);
  assert(legacy.status === 'unavailable' && legacyDisk.status === 'unavailable', 'legacy fixture writes unavailable sidecar');
  assert(Array.isArray(legacyDisk.metrics) && legacyDisk.metrics.length === 0, 'legacy sidecar has empty metrics array');
  assert(typeof legacyDisk.reason === 'string' && legacyDisk.reason.includes('raw_lap_distance_m'),
    'legacy sidecar includes clear unavailable reason', JSON.stringify(legacyDisk));
}

async function main() {
  console.log('═══ Track Outline Phase 06 Apex Metrics Export Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
