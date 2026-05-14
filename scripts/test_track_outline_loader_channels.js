/**
 * Track outline/apex Phase 02 frontend loader channel tests.
 *
 * Run: node scripts/test_track_outline_loader_channels.js
 */

'use strict';

const { chromium } = require('playwright');
const { startServer } = require('./lib/test-server');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const WEB_DIR = path.join(ROOT, 'web');

let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function buildParquet({ name, outlineColumns }) {
  const out = path.join(os.tmpdir(), `${name}-${Date.now()}-${Math.random().toString(16).slice(2)}.parquet`);
  const code = `
import pyarrow as pa, pyarrow.parquet as pq
n = 12
lap_number = [1] * n
lap_time_s = [i * 0.25 for i in range(n)]
lap_distance_m = [i * 1.0 for i in range(n)]
cols = [
  pa.array(lap_number, type=pa.int32()),
  pa.array(lap_time_s, type=pa.float32()),
  pa.array(lap_distance_m, type=pa.float32()),
  pa.array([100.0 + i for i in range(n)], type=pa.float32()),
  pa.array([0.25] * n, type=pa.float32()),
  pa.array([0.0] * n, type=pa.float32()),
  pa.array([8000.0] * n, type=pa.float32()),
  pa.array([3] * n, type=pa.int32()),
  pa.array([0.0] * n, type=pa.float32()),
  pa.array([1.0] * n, type=pa.float32()),
  pa.array([1.5] * n, type=pa.float32()),
  pa.array([20.0] * n, type=pa.float32()),
  pa.array([50.0] * n, type=pa.float32()),
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
if ${outlineColumns ? 'True' : 'False'}:
  cols.extend([
    pa.array([100.0 + i * 0.5 for i in range(n)], type=pa.float32()),
    pa.array([-2.25 if i == 1 else 1.25 for i in range(n)], type=pa.float32()),
    pa.array([7.5 if i == 1 else 8.0 for i in range(n)], type=pa.float32()),
    pa.array([5.25 if i == 1 else 6.75 for i in range(n)], type=pa.float32()),
    pa.array([10 + i for i in range(n)], type=pa.int32()),
    pa.array([20 + i for i in range(n)], type=pa.int32()),
    pa.array([30 + i for i in range(n)], type=pa.int32()),
    pa.array([40 + i for i in range(n)], type=pa.int32()),
    pa.array(['dry_fl_' + str(i) for i in range(n)], type=pa.string()),
    pa.array(['kerb_fr_' + str(i) for i in range(n)], type=pa.string()),
    pa.array(['grass_rl_' + str(i) for i in range(n)], type=pa.string()),
    pa.array(['gravel_rr_' + str(i) for i in range(n)], type=pa.string()),
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

async function runBrowserLoaderTests() {
  const futurePath = buildParquet({ name: 'loader-future', outlineColumns: true });
  const legacyAPath = buildParquet({ name: 'loader-legacy-a', outlineColumns: false });
  const legacyBPath = buildParquet({ name: 'loader-legacy-b', outlineColumns: false });
  const files = [
    { name: 'future-loader.parquet', b64: fs.readFileSync(futurePath).toString('base64') },
    { name: 'legacy-a-loader.parquet', b64: fs.readFileSync(legacyAPath).toString('base64') },
    { name: 'legacy-b-loader.parquet', b64: fs.readFileSync(legacyBPath).toString('base64') },
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
    await loadFiles(page, files);
    await page.waitForFunction(() => window.__getSessionKeys && window.__getSessionKeys().length === 3, { timeout: 10000 });

    const state = await page.evaluate(() => {
      const futureKey = window.__getSessionKeys().find(k => k.includes('future-loader.parquet'));
      const legacyAKey = window.__getSessionKeys().find(k => k.includes('legacy-a-loader.parquet'));
      const legacyBKey = window.__getSessionKeys().find(k => k.includes('legacy-b-loader.parquet'));
      const future = window.__getSessionData(futureKey);
      const legacy = window.__getSessionData(legacyAKey);
      return { futureKey, legacyAKey, legacyBKey, future, legacy };
    });

    const row = 1;
    assert(state.future.raw_lap_distance_m[row] === 100.5, 'future loader exposes raw_lap_distance_m exactly', String(state.future.raw_lap_distance_m[row]));
    assert(state.future.path_lateral_m[row] === -2.25, 'future loader exposes path_lateral_m exactly');
    assert(state.future.track_edge_m[row] === 7.5, 'future loader exposes track_edge_m exactly');
    assert(state.future.distance_to_track_edge_m[row] === 5.25, 'future loader exposes distance_to_track_edge_m exactly');
    assert(state.future.surface_type_fl[row] === 11 && state.future.surface_type_fr[row] === 21, 'future loader exposes front surface channels exactly');
    assert(state.future.surface_type_rl[row] === 31 && state.future.surface_type_rr[row] === 41, 'future loader exposes rear surface channels exactly');
    assert(state.future.terrain_name_fl[row] === 'dry_fl_1' && state.future.terrain_name_fr[row] === 'kerb_fr_1', 'future loader exposes front terrain channels exactly');
    assert(state.future.terrain_name_rl[row] === 'grass_rl_1' && state.future.terrain_name_rr[row] === 'gravel_rr_1', 'future loader exposes rear terrain channels exactly');

    assert(Array.isArray(state.legacy.raw_lap_distance_m) && state.legacy.raw_lap_distance_m.length === 0, 'legacy loader leaves missing raw_lap_distance_m empty');
    assert(state.legacy.lap_distance_m[1] === 1 && state.legacy.raw_lap_distance_m[1] === undefined, 'legacy loader does not synthesize raw_lap_distance_m from lap_distance_m');
    assert(Array.isArray(state.legacy.track_edge_m) && state.legacy.track_edge_m.length === 0, 'legacy loader leaves missing track_edge_m empty');

    const structure = await page.evaluate(({ legacyAKey, legacyBKey }) => {
      const sp = document.getElementById('session-picker');
      const rp = document.getElementById('ref-picker');
      sp.value = `${legacyAKey}::0`;
      rp.value = `${legacyBKey}::0`;
      sp.dispatchEvent(new Event('change'));
      rp.dispatchEvent(new Event('change'));
      return {
        panelLabels: [...document.querySelectorAll('#panels .panel-label')].map(el => el.textContent.replace('⠿', '').trim()),
        panelCount: document.querySelectorAll('#panels .panel-wrap').length,
        pageText: document.body.textContent,
      };
    }, { legacyAKey: state.legacyAKey, legacyBKey: state.legacyBKey });

    assert(structure.panelCount === 8, 'legacy compare structural smoke keeps existing panel count', String(structure.panelCount));
    assert(structure.panelLabels.join('|') === 'Speed (km/h)|Throttle|Brake|RPM|Gear|Steering|Slip angle FL / FR (deg)|Δt (ms, +session slower)', 'legacy compare structural smoke keeps existing panel labels', structure.panelLabels.join('|'));
    assert(!structure.pageText.includes('raw_lap_distance_m') && !structure.pageText.includes('track_edge_m'), 'legacy compare structural smoke shows no new outline UI labels');
    assert(pageErrors.length === 0, 'loader test produces no page errors', pageErrors.join(' | '));
    assert(consoleErrors.length === 0, 'loader test produces no console errors', consoleErrors.join(' | '));
  } finally {
    await browser.close();
    server.close();
  }
}

async function main() {
  console.log('═══ Track Outline Phase 02 Loader Channel Tests ═══\n');
  await runBrowserLoaderTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
