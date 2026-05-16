/**
 * F16 Bug 12 — Wheel-out should zoom out from an auto-zoomed segment.
 *
 * Auto-zoom fits the selected segment as the render base. At user scale 1x,
 * only that segment is shown. While auto-zoom is active, wheel-out should be
 * allowed to reduce user scale below 1 so the user can see more context.
 * Normal full-track mode should still clamp at scale 1.
 *
 * Run: node dev/scripts/test_f16_bug12_zoom_out_autozoom.js
 */
// @parallel true

'use strict';

const { chromium } = require('playwright');
const { startServer } = require('./lib/test-server');
const path = require('path');
const fs = require('fs');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'product', 'web');
const SESSIONS_DIR = path.join(ROOT, 'dev', 'sessions');
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', 'f16-bug12-zoom-out-report');
const SHOTS_DIR = path.join(REPORT_DIR, 'screenshots');
fs.mkdirSync(SHOTS_DIR, { recursive: true });

const SESSION_FILE = path.join(SESSIONS_DIR,
  'session_20260510T074144Z_circuit-de-barcelona_lmu.parquet');

let passCount = 0;
let failCount = 0;
const results = [];

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  results.push({ status, name, detail: String(detail) });
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

async function sampleCanvas(page, cols = 5, rows = 5) {
  return page.evaluate(({ cols, rows }) => {
    const canvas = document.getElementById('track-heatmap-canvas');
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const pixels = [];
    for (let py = 0; py < rows; py++) {
      for (let px = 0; px < cols; px++) {
        const x = Math.floor(w * (px + 1) / (cols + 1));
        const y = Math.floor(h * (py + 1) / (rows + 1));
        const d = ctx.getImageData(x, y, 1, 1).data;
        pixels.push({ r: d[0], g: d[1], b: d[2], a: d[3] });
      }
    }
    return pixels;
  }, { cols, rows });
}

function countMatching(a, b) {
  if (!a || !b) return { matches: 0, total: 0 };
  let matches = 0;
  const total = Math.min(a.length, b.length);
  for (let i = 0; i < total; i++) {
    const p1 = a[i];
    const p2 = b[i];
    if (p1.r === p2.r && p1.g === p2.g && p1.b === p2.b && p1.a === p2.a) matches++;
  }
  return { matches, total };
}

async function nextFrame(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
}

async function loadSession(page) {
  const uploadInput = await page.$('#file-input');
  await uploadInput.setInputFiles(SESSION_FILE);
  await page.waitForFunction(() => window.__getSessionKeys?.().length > 0, { timeout: 10000 });
  await page.evaluate(() => {
    const opts = [...document.getElementById('session-picker')
      .querySelectorAll('option')].filter(o => o.value);
    if (opts.length >= 2) {
      document.getElementById('session-picker').value = opts[0].value;
      document.getElementById('ref-picker').value = opts[1].value;
      document.getElementById('session-picker').dispatchEvent(new Event('change'));
    }
  });
  await page.waitForFunction(() => {
    const panels = document.querySelectorAll('#panels .panel-svg');
    const zoom = window.__getZoomRange?.();
    return panels.length >= 2 && zoom != null;
  }, { timeout: 10000 });
}

async function waitForZoomRange(page, start, end) {
  await page.waitForFunction(
    ([expectedStart, expectedEnd]) => {
      const z = window.__getZoomRange?.();
      return z && z.start === expectedStart && z.end === expectedEnd;
    },
    [start, end],
    { timeout: 2000 }
  );
  await nextFrame(page);
}

async function wheelAtCanvasCenter(page, deltaY) {
  const canvas = await page.$('#track-heatmap-canvas');
  const box = await canvas.boundingBox();
  assert(box !== null, 'wheel: canvas has bounding box');
  if (!box) return;
  await canvas.hover({ position: { x: box.width / 2, y: box.height / 2 } });
  await page.mouse.wheel(0, deltaY);
  await nextFrame(page);
}

async function runTests() {
  console.log('═══ F16 Bug 12 — Zoom out from auto-zoomed segment ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => window.__features, { timeout: 5000 });
    await loadSession(page);

    console.log('\n════ SC1: Full-track mode still clamps zoom-out at 1x ════');
    await page.evaluate(() => {
      window.__setFeatureFlag('mapZoomPan', true);
      window.__setFeatureFlag('mapAutoZoom', false);
      window.__clearZoomRange();
    });
    await page.waitForFunction(() => {
      const f = window.__features;
      const z = window.__getZoomRange?.();
      return f && f.mapZoomPan === true && f.mapAutoZoom === false && z && z.start === 0;
    }, { timeout: 2000 });
    await nextFrame(page);

    await wheelAtCanvasCenter(page, 800);
    const fullTrackState = await page.evaluate(() => window.__mapZoomPanState);
    assert(fullTrackState.scale === 1,
      'SC1: full-track zoom-out remains clamped at 1x',
      `scale=${fullTrackState.scale}`);

    const fullTrack = await sampleCanvas(page);
    assert(fullTrack !== null, 'SC1: full-track canvas sampled');

    console.log('\n════ SC2: Auto-zoomed mode allows zoom-out below 1x ════');
    await page.evaluate(() => {
      window.__setFeatureFlag('mapAutoZoom', true);
      window.__setZoomRange(300, 700);
    });
    await waitForZoomRange(page, 300, 700);

    const autoZoomed = await sampleCanvas(page);
    assert(autoZoomed !== null, 'SC2: auto-zoomed canvas sampled');
    const zoomVsFull = countMatching(fullTrack, autoZoomed);
    assert(zoomVsFull.matches < zoomVsFull.total,
      'SC2: auto-zoomed selected range differs from full-track',
      `${zoomVsFull.total - zoomVsFull.matches}/${zoomVsFull.total} pixels differ`);

    const beforeWheel = await page.evaluate(() => window.__mapZoomPanState);
    assert(beforeWheel.scale === 1,
      'SC2: auto-zoom starts at user scale 1x',
      `scale=${beforeWheel.scale}`);

    await wheelAtCanvasCenter(page, 800);

    const afterWheel = await page.evaluate(() => window.__mapZoomPanState);
    assert(afterWheel.scale < 1,
      'SC2: wheel-out lowers user scale below 1x while auto-zoom is active',
      `scale=${afterWheel.scale}`);

    const zoomedOut = await sampleCanvas(page);
    const outVsAuto = countMatching(autoZoomed, zoomedOut);
    assert(outVsAuto.matches < outVsAuto.total,
      'SC2: wheel-out changes rendered canvas from selected-segment view',
      `${outVsAuto.total - outVsAuto.matches}/${outVsAuto.total} pixels differ`);

    await page.screenshot({ path: path.join(SHOTS_DIR, 'bug12_zoomed_out_from_autozoom.png') });
  } finally {
    await browser.close();
    server.close();
  }

  const reportLines = [
    '# F16 Bug 12 — Zoom Out From Auto-Zoom Report', '',
    `Passed: ${passCount}`, `Failed: ${failCount}`, '',
    '| Status | Assertion | Detail |', '|--------|-----------|--------|',
    ...results.map(r => `| ${r.status} | ${r.name} | ${r.detail} |`),
  ];
  fs.writeFileSync(path.join(REPORT_DIR, 'REPORT.md'), reportLines.join('\n'));
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount > 0) throw new Error(`${failCount} assertions failed`);
}

runTests().catch(err => { console.error(err); process.exit(1); });
