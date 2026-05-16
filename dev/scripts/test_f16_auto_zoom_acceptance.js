/**
 * F16 Auto-Zoom — Playwright acceptance test suite.
 *
 * Validates auto-zoom behaviour end-to-end using debug hooks to avoid
 * fragile drag-select interactions (per Testing Lessons L1/L3).
 *
 * Run: node scripts/test_f16_auto_zoom_acceptance.js
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
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', 'f16-auto-zoom-acceptance-report');
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

/** Compare two pixel grids; return count of matching pixels. */
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

/** Sample a grid of pixels from the track-heatmap-canvas. */
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

/** Load session, pick laps, click Compare, wait for render. */
async function loadSessionAndCompare(page) {
  const uploadInput = await page.$('#file-input');
  await uploadInput.setInputFiles(SESSION_FILE);
  await page.waitForFunction(() => {
    const keys = window.__getSessionKeys?.();
    return keys && keys.length > 0;
  }, { timeout: 10000 });

  await page.evaluate(() => {
    const opts = [...document.getElementById('session-picker')
      .querySelectorAll('option')].filter(o => o.value);
    if (opts.length >= 2) {
      const sp = document.getElementById('session-picker');
      const rp = document.getElementById('ref-picker');
      sp.value = opts[0].value;
      rp.value = opts[1].value;
      sp.dispatchEvent(new Event('change'));
    }
  });
  // Combined readiness check: panels rendered and zoom range ready
  await page.waitForFunction(() => {
    const panels = document.querySelectorAll('#panels .panel-svg');
    const zoom = window.__getZoomRange?.();
    return panels.length >= 2 && zoom != null;
  }, { timeout: 10000 });
}

const GRID = 5; // 5×5 sampling grid

async function runTests() {
  console.log('═══ F16 Auto-Zoom — Acceptance Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => window.__features, { timeout: 5000 });
    await loadSessionAndCompare(page);

    // ── SC1: Default state — full track, no auto-zoom ──────────────────────
    console.log('\n════ SCENARIO 1: Default state ════');
    await page.evaluate(() => {
      window.__setFeatureFlag('mapLinkedHighlight', true);
      window.__setFeatureFlag('mapAutoZoom', true);
    });
    // Wait for feature flags to be applied
    await page.waitForFunction(() => {
      const f = window.__features;
      return f && f.mapLinkedHighlight === true && f.mapAutoZoom === true;
    }, { timeout: 2000 });

    // SC1: verify auto-zoom doesn't modify the map when range is full-track.
    // Batch state read in single round-trip
    const s1 = await page.evaluate(() => ({
      autoZoom: window.__features.mapAutoZoom,
      linkedHL: window.__features.mapLinkedHighlight,
      zoomStart: window.__getZoomRange().start,
      zoomEnd: window.__getZoomRange().end,
      mapState: window.__mapZoomPanState,
    }));
    assert(s1.autoZoom === true, 'SC1: mapAutoZoom enabled', String(s1.autoZoom));
    assert(s1.linkedHL === true, 'SC1: mapLinkedHighlight enabled', String(s1.linkedHL));

    // Capture full-track canvas pixels for later comparison
    const fullTrack = await sampleGrid(page, GRID, GRID);

    // ── SC2: Auto-zoom activates on zoom range ──────────────────────────────
    console.log('\n════ SCENARIO 2: Auto-zoom activates ════');
    await page.evaluate(() => window.__setZoomRange(300, 700));
    // Wait for zoom range to be applied
    await page.waitForFunction(
      ([start, end]) => {
        const z = window.__getZoomRange();
        return z && z.start === start && z.end === end;
      },
      [300, 700],
      { timeout: 2000 }
    );

    // Batch state read: zoom range + canvas pixels in one round-trip
    const s2state = await page.evaluate(() => {
      const canvas = document.getElementById('track-heatmap-canvas');
      if (!canvas) return null;
      const ctx = canvas.getContext('2d');
      const w = canvas.width, h = canvas.height;
      const GRID = 5;
      const pts = [];
      for (let py = 0; py < GRID; py++) {
        for (let px = 0; px < GRID; px++) {
          const x = Math.floor(w * (px + 1) / (GRID + 1));
          const y = Math.floor(h * (py + 1) / (GRID + 1));
          const d = ctx.getImageData(x, y, 1, 1).data;
          pts.push({ r: d[0], g: d[1], b: d[2], a: d[3] });
        }
      }
      return {
        zoom: window.__getZoomRange(),
        mapState: window.__mapZoomPanState,
        canvas: { w, h, pixels: pts },
      };
    });
    assert(s2state !== null, 'SC2: canvas state read succeeded');
    assert(s2state.zoom.start === 300, 'SC2: zoom start is 300', `start=${s2state.zoom.start}`);
    assert(s2state.zoom.end === 700, 'SC2: zoom end is 700', `end=${s2state.zoom.end}`);

    const s2pts = s2state.canvas.pixels;
    const sc2cmp = countMatching(fullTrack, s2pts);
    assert(sc2cmp.matches < sc2cmp.total,
      'SC2: canvas pixels changed after auto-zoom',
      `${sc2cmp.total - sc2cmp.matches}/${sc2cmp.total} pixels differ`);

    await page.screenshot({ path: path.join(SHOTS_DIR, 'sc2_auto_zoomed.png') });
    assert(fs.statSync(path.join(SHOTS_DIR, 'sc2_auto_zoomed.png')).size > 0,
      'SC2: screenshot written');

    // ── SC3: Auto-zoom resets on clear ──────────────────────────────────────
    console.log('\n════ SCENARIO 3: Auto-zoom resets on clear ════');
    await page.evaluate(() => window.__clearZoomRange());
    // Wait for zoom range to be cleared
    await page.waitForFunction(
      () => {
        const z = window.__getZoomRange();
        return z && z.start === 0;
      },
      [],
      { timeout: 2000 }
    );

    // Batch state read: zoom range + canvas pixels in one round-trip
    const s3state = await page.evaluate(() => {
      const canvas = document.getElementById('track-heatmap-canvas');
      if (!canvas) return null;
      const ctx = canvas.getContext('2d');
      const w = canvas.width, h = canvas.height;
      const GRID = 5;
      const pts = [];
      for (let py = 0; py < GRID; py++) {
        for (let px = 0; px < GRID; px++) {
          const x = Math.floor(w * (px + 1) / (GRID + 1));
          const y = Math.floor(h * (py + 1) / (GRID + 1));
          const d = ctx.getImageData(x, y, 1, 1).data;
          pts.push({ r: d[0], g: d[1], b: d[2], a: d[3] });
        }
      }
      return {
        zoom: window.__getZoomRange(),
        mapState: window.__mapZoomPanState,
        canvas: { w, h, pixels: pts },
      };
    });
    assert(s3state !== null, 'SC3: canvas state read succeeded');
    assert(s3state.zoom.start === 0, 'SC3: zoom starts at 0 after clear', `start=${s3state.zoom.start}`);

    const s3pts = s3state.canvas.pixels;
    const sc3cmp = countMatching(fullTrack, s3pts);
    assert(sc3cmp.matches >= sc3cmp.total * 0.8,
      'SC3: canvas returns to full-track rendering',
      `${sc3cmp.matches}/${sc3cmp.total} pixels match`);

    await page.screenshot({ path: path.join(SHOTS_DIR, 'sc3_zoom_cleared.png') });

    // ── SC4: Enabling mapAutoZoom with nothing selected doesn't move map ────
    console.log('\n════ SCENARIO 4: Toggle mapAutoZoom — no movement ════');
    await page.evaluate(() => {
      window.__setFeatureFlag('mapAutoZoom', false);
      window.__clearZoomRange();
    });
    // Wait for feature flag and zoom range to be applied
    await page.waitForFunction(() => {
      const f = window.__features;
      const z = window.__getZoomRange();
      return f && f.mapAutoZoom === false && z && z.start === 0;
    }, { timeout: 2000 });

    const s4before = await sampleGrid(page, 3, 3);

    await page.evaluate(() => window.__setFeatureFlag('mapAutoZoom', true));
    // Wait for feature flag to be applied
    await page.waitForFunction(() => {
      const f = window.__features;
      return f && f.mapAutoZoom === true;
    }, { timeout: 2000 });

    const s4after = await sampleGrid(page, 3, 3);
    const s4cmp = countMatching(s4before, s4after);
    assert(s4cmp.matches === s4cmp.total,
      'SC4: enabling mapAutoZoom with full-track range does not move map',
      `${s4cmp.matches}/${s4cmp.total} pixels match`);

    // ── SC5: computeSegmentBounds consistency ──────────────────────────────
    console.log('\n════ SCENARIO 5: computeSegmentBounds deterministic ════');
    // Batch computation in single round-trip
    const s5 = await page.evaluate(() => {
      const key = window.__getSessionKeys()[0];
      const d = window.__getSessionData(key);
      const lapA = { x: d.pos_x_m, z: d.pos_z_m };
      // Use ranges that select a meaningful subset of indices
      const range = { start: 100, end: 500 };
      const b1 = window.__computeSegmentBounds(lapA, range);
      const b2 = window.__computeSegmentBounds(lapA, range);
      return { b1, b2, range };
    });
    assert(s5.b1 !== null, 'SC5: computeSegmentBounds non-null for range 100–500');
    if (s5.b1 && s5.b2) {
      assert(s5.b1.minX === s5.b2.minX && s5.b1.maxX === s5.b2.maxX &&
             s5.b1.minZ === s5.b2.minZ && s5.b1.maxZ === s5.b2.maxZ,
        'SC5: computeSegmentBounds deterministic',
        `minX:${s5.b1.minX.toFixed(2)} vs ${s5.b2.minX.toFixed(2)}`);
    }

    // ── SC6: mapAutoZoom and mapZoomPan coexist ────────────────────────────
    console.log('\n════ SCENARIO 6: mapAutoZoom + mapZoomPan ════');
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
    const s6 = await page.evaluate(() => {
      const state = window.__mapZoomPanState;
      const zoom = window.__getZoomRange();
      return { scale: state?.scale, tx: state?.tx, ty: state?.ty, zoomStart: zoom?.start, zoomEnd: zoom?.end };
    });
    assert(s6.zoomStart === 300 && s6.zoomEnd === 700,
      'SC6: zoom range set with mapZoomPan', `start=${s6.zoomStart} end=${s6.zoomEnd}`);
    assert(s6.scale === 1, 'SC6: auto-zoom keeps scale at 1', `scale=${s6.scale}`);

    await page.screenshot({ path: path.join(SHOTS_DIR, 'sc6_zoomed_with_pan.png') });

    // Double-click resets the map and clears chart selection, like Escape
    const canvas6 = await page.$('#track-heatmap-canvas');
    await canvas6.hover({ position: { x: 5, y: 5 } });
    const box6 = await canvas6.boundingBox();
    assert(box6 !== null, 'SC6: canvas has bounding box');
    if (box6) {
      await page.mouse.dblclick(box6.x + box6.width / 2, box6.y + box6.height / 2);
      // Wait for map state to stabilize after double-click reset
      await page.waitForFunction(() => {
        const s = window.__mapZoomPanState;
        return s && s.scale === 1;
      }, { timeout: 2000 });
    }

    // Batch state read in single round-trip
    const s6dbl = await page.evaluate(() => {
      const state = window.__mapZoomPanState;
      const zoom = window.__getZoomRange();
      return { scale: state?.scale, tx: state?.tx, ty: state?.ty, zoomStart: zoom?.start, zoomEnd: zoom?.end };
    });
    assert(s6dbl.zoomStart === 0,
      'SC6: zoom range clears after dblclick',
      `start=${s6dbl.zoomStart} end=${s6dbl.zoomEnd}`);
    assert(s6dbl.scale === 1, 'SC6: scale returns to 1 after dblclick',
      `scale=${s6dbl.scale}`);

    await page.screenshot({ path: path.join(SHOTS_DIR, 'sc6_after_dblclick.png') });

    // ── SC7: Screenshot artifacts ──────────────────────────────────────────
    console.log('\n════ SCENARIO 7: Screenshot artifacts ════');
    for (const f of ['sc2_auto_zoomed.png', 'sc3_zoom_cleared.png',
                     'sc6_zoomed_with_pan.png', 'sc6_after_dblclick.png']) {
      const p = path.join(SHOTS_DIR, f);
      assert(fs.existsSync(p) && fs.statSync(p).size > 0,
        `SC7: ${f} exists and non-empty`,
        fs.existsSync(p) ? `${fs.statSync(p).size} bytes` : 'missing');
    }

  } finally {
    await browser.close();
    server.close();
  }

  // ── Report ────────────────────────────────────────────────────────────────
  const reportLines = [
    '# F16 Auto-Zoom — Acceptance Test Report', '',
    `Passed: ${passCount}`, `Failed: ${failCount}`, '',
    '| Status | Assertion | Detail |', '|--------|-----------|--------|',
    ...results.map(r => `| ${r.status} | ${r.name} | ${r.detail} |`),
  ];
  fs.writeFileSync(path.join(REPORT_DIR, 'REPORT.md'), reportLines.join('\n'));
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount > 0) throw new Error(`${failCount} assertions failed`);
}

runTests().catch(err => { console.error(err); process.exit(1); });