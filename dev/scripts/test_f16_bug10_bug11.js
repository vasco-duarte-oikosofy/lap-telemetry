/**
 * F16 Bug 10 & 11 — Fix verification tests.
 *
 * Bug 10: mapAutoZoom blocks mapZoomPan when a selection is active.
 * Bug 11: Auto-zoom doesn't update when range changes within a selection.
 *
 * Run: node scripts/test_f16_bug10_bug11.js
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
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', 'f16-bug10-bug11-report');
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
  // Combined readiness check: panels rendered and zoom range ready
  await page.waitForFunction(() => {
    const panels = document.querySelectorAll('#panels .panel-svg');
    const zoom = window.__getZoomRange?.();
    return panels.length >= 2 && zoom != null;
  }, { timeout: 10000 });
}

/** Sample canvas pixels on a grid. */
async function sampleGrid(page, cols, rows) {
  return page.evaluate(({ cols, rows }) => {
    const canvas = document.getElementById('track-heatmap-canvas');
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const pts = [];
    for (let py = 0; py < rows; py++) {
      for (let px = 0; px < cols; px++) {
        const x = Math.floor(w * (px + 1) / (cols + 1));
        const y = Math.floor(h * (py + 1) / (rows + 1));
        const d = ctx.getImageData(x, y, 1, 1).data;
        pts.push({ r: d[0], g: d[1], b: d[2], a: d[3] });
      }
    }
    return pts;
  }, { cols, rows });
}

/** Analyze full canvas: sample pixels at fixed positions. */
async function analyzeCanvas(page) {
  return page.evaluate(() => {
    const canvas = document.getElementById('track-heatmap-canvas');
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    // Sample a 10x10 grid for better coverage
    const cols = 10, rows = 10;
    const pixels = [];
    for (let py = 0; py < rows; py++) {
      for (let px = 0; px < cols; px++) {
        const x = Math.floor(w * (px + 1) / (cols + 1));
        const y = Math.floor(h * (py + 1) / (rows + 1));
        const d = ctx.getImageData(x, y, 1, 1).data;
        pixels.push({ r: d[0], g: d[1], b: d[2], a: d[3] });
      }
    }
    return { w, h, pixels };
  });
}

/** Compare two canvas analyses; return count of differing pixels. */
function compareCanvas(a, b) {
  if (!a || !b || !a.pixels || !b.pixels) return { diff: 0, total: 0 };
  let diff = 0;
  const total = a.pixels.length;
  for (let i = 0; i < total; i++) {
    const p1 = a.pixels[i], p2 = b.pixels[i];
    if (p1.a !== p2.a || p1.r !== p2.r || p1.g !== p2.g || p1.b !== p2.b) diff++;
  }
  return { diff, total };
}

/** Count matching pixels between two grids. */
function countMatching(a, b) {
  if (!a || !b) return { matches: 0, total: 0 };
  let matches = 0;
  const total = a.length;
  for (let i = 0; i < total; i++) {
    if (a[i].r === b[i].r && a[i].g === b[i].g &&
        a[i].b === b[i].b && a[i].a === b[i].a) matches++;
  }
  return { matches, total };
}

async function runTests() {
  console.log('═══ F16 Bug 10 & 11 — Fix Verification Tests ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => window.__features, { timeout: 5000 });
    await loadSession(page);

    // ── BUG 10: mapAutoZoom blocks mapZoomPan panning ──────────────────────
    console.log('\n════ BUG 10: mapAutoZoom blocks mapZoomPan ════');

    // Enable both mapZoomPan and mapAutoZoom with a zoom range (auto-zoom active)
    await page.evaluate(() => {
      window.__setFeatureFlag('mapZoomPan', true);
      window.__setFeatureFlag('mapAutoZoom', true);
      window.__setZoomRange(300, 700);
    });
    // Wait for zoom range to be applied
    await page.waitForFunction(
      ([start, end]) => {
        const z = window.__getZoomRange();
        return z && z.start === start && z.end === end;
      },
      [300, 700],
      { timeout: 2000 }
    );

    // Batch state read in single round-trip
    const b10_state0 = await page.evaluate(() => ({
      mapState: window.__mapZoomPanState,
      zoom: window.__getZoomRange(),
    }));
    assert(b10_state0.mapState !== undefined, 'B10: mapZoomPanState exists');
    assert(b10_state0.zoom.start === 300 && b10_state0.zoom.end === 700,
      'B10: zoom range is set', `start=${b10_state0.zoom.start} end=${b10_state0.zoom.end}`);

    // Try to pan the map — should work (user pan composes on top of auto-zoom)
    const canvas10 = await page.$('#track-heatmap-canvas');
    await canvas10.hover({ position: { x: 5, y: 5 } });
    const box10 = await canvas10.boundingBox();
    assert(box10 !== null, 'B10: canvas has bounding box');

    if (box10) {
      // Pan right by 100px
      await page.mouse.move(box10.x + 50, box10.y + 50);
      await page.mouse.down();
      await page.mouse.move(box10.x + 150, box10.y + 50, { steps: 10 });
      await page.mouse.up();
      // Wait for pan state to stabilize
      await page.waitForFunction(() => window.__mapZoomPanState != null, { timeout: 2000 });

      const b10_afterPan = await page.evaluate(() => window.__mapZoomPanState);
      // The pan should NOT be reset to 0 — the user's pan should persist
      assert(b10_afterPan.tx !== 0,
        'B10: user pan persists with auto-zoom active',
        `tx=${b10_afterPan.tx} (expected ≠ 0)`);
    }

    await page.screenshot({ path: path.join(SHOTS_DIR, 'bug10_pan_with_autozoom.png') });

    // ── BUG 10 follow-up: panning with no selection should also work ──────
    console.log('\n════ BUG 10 follow-up: pan with no selection ════');
    await page.evaluate(() => window.__clearZoomRange());
    // Wait for zoom range to be cleared
    await page.waitForFunction(
      () => {
        const z = window.__getZoomRange();
        return z && z.start === 0 && z.end === 4650; // full track
      },
      [],
      { timeout: 2000 }
    );

    // Reset user transform before testing
    const canvas10b = await page.$('#track-heatmap-canvas');
    const box10b = await canvas10b.boundingBox();
    if (box10b) {
      // Double-click to reset any existing pan
      await page.mouse.dblclick(box10b.x + box10b.width / 2, box10b.y + box10b.height / 2);
      await page.waitForFunction(() => {
        const s = window.__mapZoomPanState;
        return s && s.tx === 0 && s.ty === 0;
      }, { timeout: 2000 });
    }

    const b10b_state0 = await page.evaluate(() => window.__mapZoomPanState);
    assert(b10b_state0.tx === 0 && b10b_state0.ty === 0,
      'B10: pan reset to 0 before test', `tx=${b10b_state0.tx} ty=${b10b_state0.ty}`);

    // Pan with full-track range (auto-zoom inactive)
    await page.mouse.move(box10b.x + 50, box10b.y + 50);
    await page.mouse.down();
    await page.mouse.move(box10b.x + 200, box10b.y + 50, { steps: 10 });
    await page.mouse.up();
    await page.waitForFunction(() => window.__mapZoomPanState != null, { timeout: 2000 });

    const b10b_afterPan = await page.evaluate(() => window.__mapZoomPanState);
    assert(b10b_afterPan.tx !== 0,
      'B10: pan works with full-track range',
      `tx=${b10b_afterPan.tx} (expected ≠ 0)`);

    // ── BUG 11: auto-zoom doesn't update when range changes ──────────────
    console.log('\n════ BUG 11: auto-zoom updates when range changes ════');

    // Re-acquire canvas after any re-renders
    const canvas11 = await page.$('#track-heatmap-canvas');
    assert(canvas11 !== null, 'B11: canvas exists');

    // Enable auto-zoom and set initial range
    await page.evaluate(() => {
      window.__setFeatureFlag('mapAutoZoom', true);
      window.__setZoomRange(1000, 2000);
    });
    // Wait for zoom range to be applied
    await page.waitForFunction(
      ([start, end]) => {
        const z = window.__getZoomRange();
        return z && z.start === start && z.end === end;
      },
      [1000, 2000],
      { timeout: 2000 }
    );

    // Batch state read: zoom range + canvas analysis in one round-trip
    const b11_state1 = await page.evaluate(() => {
      const canvas = document.getElementById('track-heatmap-canvas');
      if (!canvas) return null;
      const ctx = canvas.getContext('2d');
      const w = canvas.width, h = canvas.height;
      const pixels = [];
      for (let py = 0; py < 10; py++) {
        for (let px = 0; px < 10; px++) {
          const x = Math.floor(w * (px + 1) / 11);
          const y = Math.floor(h * (py + 1) / 11);
          const d = ctx.getImageData(x, y, 1, 1).data;
          pixels.push({ r: d[0], g: d[1], b: d[2], a: d[3] });
        }
      }
      return {
        zoom: window.__getZoomRange(),
        mapState: window.__mapZoomPanState,
        canvas: { w, h, pixels },
      };
    });
    assert(b11_state1 !== null, 'B11: canvas analysis 1 succeeded');
    assert(b11_state1.zoom.start === 1000 && b11_state1.zoom.end === 2000,
      'B11: initial range set', `start=${b11_state1.zoom.start} end=${b11_state1.zoom.end}`);
    const b11_analysis1 = b11_state1.canvas;

    // Change to a dramatically different range — auto-zoom should update
    await page.evaluate(() => window.__setZoomRange(3000, 4000));
    // Wait for zoom range to be applied
    await page.waitForFunction(
      ([start, end]) => {
        const z = window.__getZoomRange();
        return z && z.start === start && z.end === end;
      },
      [3000, 4000],
      { timeout: 2000 }
    );

    // Batch state read: zoom range + canvas analysis in one round-trip
    const b11_state2 = await page.evaluate(() => {
      const canvas = document.getElementById('track-heatmap-canvas');
      if (!canvas) return null;
      const ctx = canvas.getContext('2d');
      const w = canvas.width, h = canvas.height;
      const pixels = [];
      for (let py = 0; py < 10; py++) {
        for (let px = 0; px < 10; px++) {
          const x = Math.floor(w * (px + 1) / 11);
          const y = Math.floor(h * (py + 1) / 11);
          const d = ctx.getImageData(x, y, 1, 1).data;
          pixels.push({ r: d[0], g: d[1], b: d[2], a: d[3] });
        }
      }
      return {
        zoom: window.__getZoomRange(),
        mapState: window.__mapZoomPanState,
        canvas: { w, h, pixels },
      };
    });
    assert(b11_state2 !== null, 'B11: canvas analysis 2 succeeded');
    assert(b11_state2.zoom.start === 3000 && b11_state2.zoom.end === 4000,
      'B11: second range set', `start=${b11_state2.zoom.start} end=${b11_state2.zoom.end}`);
    const b11_analysis2 = b11_state2.canvas;

    // The map should show a different portion of track
    const cmp1 = compareCanvas(b11_analysis1, b11_analysis2);
    assert(cmp1.diff >= 5,
      'B11: map updates when range changes',
      `${cmp1.diff}/${cmp1.total} pixels differ`);

    // Now narrow the range further (sub-selection)
    await page.evaluate(() => window.__setZoomRange(3200, 3600));
    // Wait for zoom range to be applied
    await page.waitForFunction(
      ([start, end]) => {
        const z = window.__getZoomRange();
        return z && z.start === start && z.end === end;
      },
      [3200, 3600],
      { timeout: 2000 }
    );

    const b11_analysis3 = await analyzeCanvas(page);

    // Narrowing should change the view
    const cmp2 = compareCanvas(b11_analysis2, b11_analysis3);
    assert(cmp2.diff >= 3,
      'B11: narrowing range changes map view',
      `${cmp2.diff}/${cmp2.total} pixels differ`);

    await page.screenshot({ path: path.join(SHOTS_DIR, 'bug11_range_change.png') });

  } finally {
    await browser.close();
    server.close();
  }

  // ── Report ────────────────────────────────────────────────────────────────
  const reportLines = [
    '# F16 Bug 10 & 11 — Fix Verification Report', '',
    `Passed: ${passCount}`, `Failed: ${failCount}`, '',
    '| Status | Assertion | Detail |', '|--------|-----------|--------|',
    ...results.map(r => `| ${r.status} | ${r.name} | ${r.detail} |`),
  ];
  fs.writeFileSync(path.join(REPORT_DIR, 'REPORT.md'), reportLines.join('\n'));
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount > 0) throw new Error(`${failCount} assertions failed`);
}

runTests().catch(err => { console.error(err); process.exit(1); });