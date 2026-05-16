/**
 * Track outline/apex Phase 00 schema compatibility tests.
 *
 * Run: node scripts/test_track_outline_schema_compat.js
 */

'use strict';

const { chromium } = require('playwright');
const { startServer } = require('./lib/test-server');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'product', 'web');

let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function buildParquet({ futureColumns }) {
  const out = path.join(os.tmpdir(), `outline-schema-${futureColumns ? 'future' : 'legacy'}-${Date.now()}-${Math.random().toString(16).slice(2)}.parquet`);
  const code = `
import pyarrow as pa, pyarrow.parquet as pq
n = 24
lap_number = [1] * n
lap_time_s = [i * 0.2 for i in range(n)]
lap_distance_m = [i * 10.0 for i in range(n)]
speed_kph = [120.0 + i for i in range(n)]
cols = [
  pa.array(lap_number, type=pa.int32()),
  pa.array(lap_time_s, type=pa.float32()),
  pa.array(lap_distance_m, type=pa.float32()),
  pa.array(speed_kph, type=pa.float32()),
  pa.array([0.5] * n, type=pa.float32()),
  pa.array([0.0] * n, type=pa.float32()),
  pa.array([9000.0] * n, type=pa.float32()),
  pa.array([4] * n, type=pa.int32()),
  pa.array([0.0] * n, type=pa.float32()),
  pa.array([1.0] * n, type=pa.float32()),
  pa.array([1.1] * n, type=pa.float32()),
  pa.array([30.0] * n, type=pa.float32()),
  pa.array([70.0] * n, type=pa.float32()),
  pa.array([float(i) for i in range(n)], type=pa.float32()),
  pa.array([float(i) * 0.5 for i in range(n)], type=pa.float32()),
  pa.array([False] * n, type=pa.bool_()),
  pa.array([False] * n, type=pa.bool_()),
]
names = [
  'lap_number', 'lap_time_s', 'lap_distance_m', 'speed_kph',
  'throttle_norm', 'brake_norm', 'engine_rpm', 'gear',
  'steering_norm', 'slip_angle_fl_deg', 'slip_angle_fr_deg',
  'last_sector_1_s', 'last_sector_2_s', 'pos_x_m', 'pos_z_m',
  'abs_active', 'tc_active',
]
if ${futureColumns ? 'True' : 'False'}:
  raw = [d + 0.25 for d in lap_distance_m]
  lateral = [(-1.0 if i % 2 == 0 else 1.0) for i in range(n)]
  edge = [7.0] * n
  cols.extend([
    pa.array(raw, type=pa.float32()),
    pa.array(lateral, type=pa.float32()),
    pa.array(edge, type=pa.float32()),
    pa.array([e - abs(l) for e, l in zip(edge, lateral)], type=pa.float32()),
    pa.array([0] * n, type=pa.int32()),
    pa.array([1] * n, type=pa.int32()),
    pa.array([2] * n, type=pa.int32()),
    pa.array([3] * n, type=pa.int32()),
    pa.array(['dry'] * n, type=pa.string()),
    pa.array(['kerb'] * n, type=pa.string()),
    pa.array(['grass'] * n, type=pa.string()),
    pa.array(['gravel'] * n, type=pa.string()),
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
  if (res.error || res.status !== 0) {
    throw new Error(`pyarrow fixture failed: ${res.error?.message || res.stderr}`);
  }
  return out;
}

async function loadFiles(page, files) {
  await page.evaluate(async ({ files }) => {
    const dt = new DataTransfer();
    for (const f of files) {
      const bin = Uint8Array.from(atob(f.b64), c => c.charCodeAt(0));
      dt.items.add(new File([bin], f.name, { type: 'application/octet-stream' }));
    }
    const input = document.getElementById('file-input');
    input.files = dt.files;
    input.dispatchEvent(new Event('change'));
  }, { files });
}

async function runPureModuleTests() {
  const mod = await import(path.join(ROOT, 'product/web/js/trackOutlineChannels.js'));
  const legacy = { lap_distance_m: [10, 20] };
  const future = {
    raw_lap_distance_m: [10.25, 20.25],
    path_lateral_m: [-1, 1],
    track_edge_m: [7, 7],
    lap_distance_m: [10, 20],
  };

  assert(mod.TRACK_OUTLINE_CHANNELS.includes('raw_lap_distance_m'), 'outline channel list includes raw_lap_distance_m');
  assert(mod.hasTrackOutlineChannels(future), 'future-shaped data reports outline channels available');
  assert(!mod.hasTrackOutlineChannels(legacy), 'legacy data reports outline channels unavailable');
  assert(mod.rawLapDistanceAt(future, 1) === 20.25, 'rawLapDistanceAt uses raw_lap_distance_m when present');
  assert(mod.rawLapDistanceAt(legacy, 1) === null, 'rawLapDistanceAt does not silently fall back by default');
  assert(mod.rawLapDistanceAt(legacy, 1, { allowIntegratedFallback: true }) === 20, 'rawLapDistanceAt falls back only when explicitly allowed');
}

async function runBrowserLoadTests() {
  const legacyPath = buildParquet({ futureColumns: false });
  const futurePath = buildParquet({ futureColumns: true });
  const files = [
    { name: 'legacy-outline-compat.parquet', b64: fs.readFileSync(legacyPath).toString('base64') },
    { name: 'future-outline-compat.parquet', b64: fs.readFileSync(futurePath).toString('base64') },
  ];

  const { server, port } = await startServer(WEB_DIR);
  const browser = await chromium.launch({ headless: true });
  const pageErrors = [];
  const consoleErrors = [];

  try {
    const page = await browser.newPage();
    page.on('pageerror', err => pageErrors.push(err.message));
    page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });

    await page.goto(`http://127.0.0.1:${port}`);
    const initialPanelText = await page.$eval('#panels', el => el.textContent);
    await loadFiles(page, files);
    await page.waitForFunction(() => window.__getSessionKeys && window.__getSessionKeys().length === 2, { timeout: 10000 });

    const keys = await page.evaluate(() => window.__getSessionKeys());
    const status = await page.$eval('#load-status', el => el.textContent);
    const finalPanelText = await page.$eval('#panels', el => el.textContent);

    assert(keys.length === 2, 'legacy and future-shaped parquet fixtures both load', keys.join(', '));
    assert(status.includes('2 file(s) loaded'), 'load status reports both files loaded', status);
    assert(pageErrors.length === 0, 'loading fixtures produces no page errors', pageErrors.join(' | '));
    assert(consoleErrors.length === 0, 'loading fixtures produces no console errors', consoleErrors.join(' | '));
    assert(finalPanelText === initialPanelText, 'loading compatibility fixtures does not render new panels before compare');
  } finally {
    await browser.close();
    server.close();
  }
}

async function main() {
  console.log('═══ Track Outline Phase 00 Schema Compatibility Tests ═══\n');
  await runPureModuleTests();
  await runBrowserLoadTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
