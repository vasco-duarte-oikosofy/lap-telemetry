/**
 * F16 Bug 5 — Double-click reset should restore full-track view with mapAutoZoom on.
 *
 * Expected semantic: double-click resets the MAP view to full-track, matching
 * existing mapZoomPan behavior. With mapAutoZoom active, the zoom indicator and
 * __mapZoomPanState.scale can still be 1x while only the selected segment is
 * shown, so this test validates the rendered canvas, not scale.
 *
 * Run: node dev/scripts/test_f16_bug5_doubleclick_reset.js
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
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', 'f16-bug5-doubleclick-report');
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
    if (p1.r === p2.r && p1.g === p2.g && p1.b === p2.b && p1.a === p2.a) {
      matches++;
    }
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

async function runTests() {
  console.log('═══ F16 Bug 5 — Double-click resets auto-zoomed map to full track ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => window.__features, { timeout: 5000 });
    await loadSession(page);

    console.log('\n════ Setup: capture full-track baseline ════');
    await page.evaluate(() => {
      window.__setFeatureFlag('mapZoomPan', true);
      window.__setFeatureFlag('mapLinkedHighlight', true);
      window.__setFeatureFlag('mapAutoZoom', false);
      window.__clearZoomRange();
    });
    await page.waitForFunction(() => {
      const f = window.__features;
      const z = window.__getZoomRange?.();
      return f && f.mapZoomPan === true && f.mapAutoZoom === false && z && z.start === 0;
    }, { timeout: 2000 });
    await nextFrame(page);

    const fullTrack = await sampleCanvas(page);
    assert(fullTrack !== null, 'baseline: full-track canvas sampled');
    await page.screenshot({ path: path.join(SHOTS_DIR, 'bug5_full_track_baseline.png') });

    console.log('\n════ Step 1: activate mapAutoZoom for selected range ════');
    await page.evaluate(() => {
      window.__setFeatureFlag('mapAutoZoom', true);
      window.__setZoomRange(300, 700);
    });
    await waitForZoomRange(page, 300, 700);

    const autoZoomed = await sampleCanvas(page);
    assert(autoZoomed !== null, 'auto-zoom: canvas sampled');
    const zoomVsFull = countMatching(fullTrack, autoZoomed);
    assert(zoomVsFull.matches < zoomVsFull.total,
      'auto-zoom: selected range view differs from full-track baseline',
      `${zoomVsFull.total - zoomVsFull.matches}/${zoomVsFull.total} pixels differ`);
    await page.screenshot({ path: path.join(SHOTS_DIR, 'bug5_auto_zoomed.png') });

    console.log('\n════ Step 2: double-click should restore full-track map view ════');
    const canvas = await page.$('#track-heatmap-canvas');
    const box = await canvas.boundingBox();
    assert(box !== null, 'double-click: canvas has bounding box');
    if (box) {
      await page.mouse.dblclick(box.x + box.width / 2, box.y + box.height / 2);
      await nextFrame(page);
    }

    const afterDblClick = await sampleCanvas(page);
    assert(afterDblClick !== null, 'double-click: post-reset canvas sampled');

    const afterVsZoom = countMatching(autoZoomed, afterDblClick);
    assert(afterVsZoom.matches < afterVsZoom.total,
      'double-click: view changes from auto-zoomed segment',
      `${afterVsZoom.total - afterVsZoom.matches}/${afterVsZoom.total} pixels differ`);

    const afterVsFull = countMatching(fullTrack, afterDblClick);
    assert(afterVsFull.matches >= afterVsFull.total * 0.8,
      'double-click: view matches full-track baseline despite mapAutoZoom being enabled',
      `${afterVsFull.matches}/${afterVsFull.total} pixels match full-track baseline`);

    const chartZoom = await page.evaluate(() => window.__getZoomRange());
    assert(chartZoom.start === 300 && chartZoom.end === 700,
      'double-click: chart zoom range persists while map view resets',
      `start=${chartZoom.start} end=${chartZoom.end}`);
    await page.screenshot({ path: path.join(SHOTS_DIR, 'bug5_after_doubleclick.png') });

    console.log('\n════ Step 3: changing chart range re-enables auto-zoom ════');
    await page.evaluate(() => window.__setZoomRange(1000, 2000));
    await waitForZoomRange(page, 1000, 2000);
    const changedRange = await sampleCanvas(page);
    const changedVsFull = countMatching(fullTrack, changedRange);
    assert(changedVsFull.matches < changedVsFull.total,
      'range change: auto-zoom reactivates after double-click suppression',
      `${changedVsFull.total - changedVsFull.matches}/${changedVsFull.total} pixels differ from full-track`);
  } finally {
    await browser.close();
    server.close();
  }

  const reportLines = [
    '# F16 Bug 5 — Double-Click Reset Report', '',
    `Passed: ${passCount}`, `Failed: ${failCount}`, '',
    '| Status | Assertion | Detail |', '|--------|-----------|--------|',
    ...results.map(r => `| ${r.status} | ${r.name} | ${r.detail} |`),
  ];
  fs.writeFileSync(path.join(REPORT_DIR, 'REPORT.md'), reportLines.join('\n'));
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount > 0) throw new Error(`${failCount} assertions failed`);
}

runTests().catch(err => { console.error(err); process.exit(1); });
