/**
 * Track outline Phase 05 apex metrics UI render tests.
 *
 * Run: node scripts/test_apex_metrics_ui.js
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
lap_number = [1]*7 + [2]*7
s = [0.0, 90.0, 101.0, 150.0, 250.0, 298.0, 400.0] * 2
lap_time_s = [i * 0.5 for i in range(7)] + [i * 0.5 for i in range(7)]
cols = [
  pa.array(lap_number, type=pa.int32()),
  pa.array(lap_time_s, type=pa.float32()),
  pa.array(s, type=pa.float32()),
  pa.array([120.0 + i for i in range(14)], type=pa.float32()),
  pa.array([0.5] * 14, type=pa.float32()),
  pa.array([0.1] * 14, type=pa.float32()),
  pa.array([7000.0] * 14, type=pa.float32()),
  pa.array([3] * 14, type=pa.int32()),
  pa.array([0.0] * 14, type=pa.float32()),
  pa.array([float(i) for i in range(14)], type=pa.float32()),
  pa.array([float(i) * 0.25 for i in range(14)], type=pa.float32()),
]
names = [
  'lap_number', 'lap_time_s', 'lap_distance_m', 'speed_kph',
  'throttle_norm', 'brake_norm', 'engine_rpm', 'gear',
  'steering_norm', 'pos_x_m', 'pos_z_m',
]
if ${outlineColumns ? 'True' : 'False'}:
  distance = [6.0] * 14
  distance[2] = 4.25
  distance[5] = 3.50
  distance[9] = 4.75
  distance[12] = 3.75
  surface_fl = [10] * 14
  surface_fr = [20] * 14
  terrain_fl = ['asphalt'] * 14
  terrain_fr = ['asphalt'] * 14
  surface_fr[2] = 21
  terrain_fr[2] = 'kerb'
  surface_fl[5] = 11
  terrain_fl[5] = 'grass'
  cols.extend([
    pa.array(s, type=pa.float32()),
    pa.array([1.0] * 14, type=pa.float32()),
    pa.array([7.0] * 14, type=pa.float32()),
    pa.array(distance, type=pa.float32()),
    pa.array(surface_fl, type=pa.int32()),
    pa.array(surface_fr, type=pa.int32()),
    pa.array([30] * 14, type=pa.int32()),
    pa.array([40] * 14, type=pa.int32()),
    pa.array(terrain_fl, type=pa.string()),
    pa.array(terrain_fr, type=pa.string()),
    pa.array(['asphalt'] * 14, type=pa.string()),
    pa.array(['asphalt'] * 14, type=pa.string()),
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

function annotation(trackId = 'spa-test') {
  return {
    track_id: trackId,
    layout_id: 'default',
    corners: [
      { id: 't1', name: 'La Source', s_start_m: 80, apex_s_m: 100, s_end_m: 120, apex_side: 'right' },
      { id: 't2', name: 'Eau Rouge', s_start_m: 280, apex_s_m: 300, s_end_m: 320, apex_side: 'left' },
    ],
  };
}

function sidecar(track = 'spa-test') {
  return { schema_version: '2', track, layout_id: 'default', vehicle_name: 'Fixture GT3' };
}

async function loadFiles(page, files) {
  await page.evaluate(async ({ files }) => {
    const dt = new DataTransfer();
    for (const f of files) {
      const bin = Uint8Array.from(atob(f.b64), c => c.charCodeAt(0));
      dt.items.add(new File([bin], f.name, { type: f.type || 'application/octet-stream' }));
    }
    const input = document.getElementById('file-input');
    input.files = dt.files;
    input.dispatchEvent(new Event('change'));
  }, { files });
}

async function compareFirstTwoLaps(page) {
  await page.evaluate(() => window.__setFeatureFlag('apexMetricsUi', true));
  const values = await page.evaluate(() => {
    const options = [...document.querySelectorAll('#session-picker option')].filter(o => o.value);
    const sp = document.getElementById('session-picker');
    const rp = document.getElementById('ref-picker');
    sp.value = options[0].value;
    rp.value = options[1].value;
    sp.dispatchEvent(new Event('change'));
    rp.dispatchEvent(new Event('change'));
    return { session: sp.value, ref: rp.value };
  });
  await page.waitForFunction(() => document.querySelectorAll('#panels .panel-wrap').length > 0, { timeout: 5000 });
  return values;
}

function fileFromPath(name, filePath) {
  return { name, b64: fs.readFileSync(filePath).toString('base64') };
}

function jsonFile(name, value) {
  return { name, b64: Buffer.from(JSON.stringify(value)).toString('base64'), type: 'application/json' };
}

async function newLoadedPage(browser, port, files) {
  const page = await browser.newPage();
  const pageErrors = [];
  const consoleErrors = [];
  page.on('pageerror', err => pageErrors.push(err.message));
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  await page.goto(`http://127.0.0.1:${port}`);
  await loadFiles(page, files);
  await page.waitForFunction(count => window.__getSessionKeys && window.__getSessionKeys().length === count, files.filter(f => f.name.endsWith('.parquet')).length, { timeout: 10000 });
  return { page, pageErrors, consoleErrors };
}

async function runBrowserTests() {
  const configuredPath = buildParquet({ name: 'apex-ui-configured', outlineColumns: true });
  const unconfiguredPath = buildParquet({ name: 'apex-ui-unconfigured', outlineColumns: true });
  const legacyPath = buildParquet({ name: 'apex-ui-legacy', outlineColumns: false });
  const { server, port } = await startServer(WEB_DIR);
  const browser = await chromium.launch({ headless: true });

  try {
    {
      const ctx = await newLoadedPage(browser, port, [
        fileFromPath('configured.parquet', configuredPath),
        jsonFile('configured.json', sidecar('spa-test')),
        jsonFile('spa-apex.json', annotation('spa-test')),
      ]);
      await compareFirstTwoLaps(ctx.page);
      const text = await ctx.page.$eval('#apex-metrics-panel', el => el.textContent.replace(/\s+/g, ' ').trim());
      console.log(`  Apex panel text: ${text}`);
      assert(text.includes('Showing selected session lap only: Lap 1 (lap# 1); reference lap is not included.'),
        'configured UI explains metrics are for the selected session lap only', text);
      assert(text.includes('La Source') && text.includes('Lap 1 (lap# 1)') && text.includes('4.25 m'), 'configured UI shows La Source lap and apex distance');
      assert(text.includes('Eau Rouge') && text.includes('3.50 m'), 'configured UI shows second corner row');
      const tableState = await ctx.page.$eval('#apex-metrics-panel', panel => {
        const table = panel.querySelector('table.apex-metrics-table');
        const firstHeader = table?.querySelector('thead th');
        const firstCell = table?.querySelector('tbody td');
        const headerBox = firstHeader?.getBoundingClientRect();
        const cellBox = firstCell?.getBoundingClientRect();
        return {
          hasTable: !!table,
          columnCount: table?.querySelectorAll('thead th').length || 0,
          firstColumnAlignedPx: headerBox && cellBox ? Math.abs(headerBox.left - cellBox.left) : null,
          widthFillsContent: table ? Math.abs(table.getBoundingClientRect().width - (panel.clientWidth - parseFloat(getComputedStyle(panel).paddingLeft) - parseFloat(getComputedStyle(panel).paddingRight))) <= 1 : false,
        };
      });
      assert(tableState.hasTable && tableState.columnCount === 6, 'configured UI renders apex metrics as a six-column HTML table', JSON.stringify(tableState));
      assert(tableState.firstColumnAlignedPx !== null && tableState.firstColumnAlignedPx <= 1,
        'configured UI table cells align under column headers', JSON.stringify(tableState));
      assert(tableState.widthFillsContent, 'configured UI table spans the panel content width for readable columns', JSON.stringify(tableState));
      assert(text.includes('late 1.00 m'), 'configured UI labels positive timing as late');
      assert(text.includes('early 2.00 m'), 'configured UI labels negative timing as early');
      assert(text.includes('21') && text.includes('kerb'), 'configured UI shows right-side surface and terrain');
      assert(text.includes('11') && text.includes('grass'), 'configured UI shows left-side surface and terrain');
      assert(ctx.pageErrors.length === 0, 'configured UI has no page errors', ctx.pageErrors.join(' | '));
      assert(ctx.consoleErrors.length === 0, 'configured UI has no console errors', ctx.consoleErrors.join(' | '));
      await ctx.page.close();
    }

    {
      const ctx = await newLoadedPage(browser, port, [
        fileFromPath('unconfigured.parquet', unconfiguredPath),
        jsonFile('unconfigured.json', sidecar('unknown-track')),
        jsonFile('spa-apex.json', annotation('spa-test')),
      ]);
      await compareFirstTwoLaps(ctx.page);
      const text = await ctx.page.$eval('#apex-metrics-panel', el => el.textContent);
      assert(text.includes('No apex annotations for this track/layout'), 'unconfigured track shows no-annotation empty state');
      await ctx.page.close();
    }

    {
      const ctx = await newLoadedPage(browser, port, [
        fileFromPath('legacy.parquet', legacyPath),
        jsonFile('legacy.json', sidecar('spa-test')),
        jsonFile('spa-apex.json', annotation('spa-test')),
      ]);
      await compareFirstTwoLaps(ctx.page);
      const state = await ctx.page.evaluate(() => ({
        apexText: document.getElementById('apex-metrics-panel').textContent,
        panelCount: document.querySelectorAll('#panels .panel-wrap').length,
        legendVisible: document.getElementById('legend').classList.contains('visible'),
      }));
      assert(state.apexText.includes('Record a new session to capture track-edge channels'), 'legacy fixture shows missing-channel empty state');
      assert(state.panelCount === 8 && state.legendVisible, 'legacy fixture keeps existing compare UI working', `${state.panelCount} panels`);
      await ctx.page.close();
    }
  } finally {
    await browser.close();
    server.close();
  }
}

async function main() {
  console.log('═══ Track Outline Phase 05 Apex Metrics UI Tests ═══\n');
  await runBrowserTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
