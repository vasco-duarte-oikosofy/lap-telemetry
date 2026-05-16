// F8–F11 test suite — ABS/TC panels, draggable reorder, Y-axis legibility, gear height
//
// Run: node scripts/test_f8f9f10f11.js
//
// SESSION_A: 142624Z (6 laps, gear 0-6, pre-M6, no ABS/TC cols)
// SESSION_B: 143916Z (3 laps, post-M6, real abs/tc, slip data)

'use strict';

const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');

// ── Paths ─────────────────────────────────────────────────────────────────────
const ROOT         = path.resolve(__dirname, '..', '..');
const HTML_FILE    = path.join(ROOT, 'web', 'compare.html');
const SESSIONS_DIR = path.join(ROOT, 'dev', 'sessions');
const REPORT_DIR   = path.join(ROOT, 'var', 'test-output', 'f8f9f10f11-test-report');
const SHOTS_DIR    = path.join(REPORT_DIR, 'screenshots');

const SESSION_A = path.join(SESSIONS_DIR, 'session_20260510T142624Z_circuit-de-barcelona_lmu.parquet');
const SESSION_B = path.join(SESSIONS_DIR, 'session_20260511T143916Z_circuit-de-barcelona_lmu.parquet');

fs.mkdirSync(SHOTS_DIR, { recursive: true });

// ── HTTP server ───────────────────────────────────────────────────────────────
function startServer() {
  const server = http.createServer((req, res) => {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end(fs.readFileSync(HTML_FILE));
  });
  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port }));
  });
}

// ── Test utilities ────────────────────────────────────────────────────────────
const results = [];
let failCount = 0;
const consoleLogs = [];

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failCount++;
  results.push({ status, name, detail });
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
  return cond;
}

async function screenshot(page, name) {
  await page.screenshot({ path: path.join(SHOTS_DIR, `${name}.png`) });
}

function setupPageLogging(page) {
  page.on('console', m => {
    const e = `[${m.type()}] ${m.text()}`;
    consoleLogs.push(e);
    if (m.type() === 'error') console.warn(`  ✖ ${e}`);
  });
  page.on('pageerror', err => {
    consoleLogs.push(`[pageerror] ${err.message}`);
    console.error(`  ✖ PAGE ERROR: ${err.message}`);
  });
}

async function loadFiles(page, filePaths) {
  const files = filePaths.map(fp => ({
    name: path.basename(fp),
    b64: fs.readFileSync(fp).toString('base64'),
  }));
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
  await page.waitForFunction(() =>
    document.querySelectorAll('.badge.loading').length === 0, { timeout: 15000 });
}

// Return the Nth non-empty picker option value (0-indexed)
async function getPickerValue(page, n) {
  return page.evaluate(n => {
    const opts = Array.from(document.querySelectorAll('#session-picker option[value]'))
      .filter(o => o.value);
    return opts[n]?.value ?? null;
  }, n);
}

async function compare(page, sessionVal, refVal) {
  await page.evaluate(({ sv, rv }) => {
    document.getElementById('session-picker').value = sv;
    document.getElementById('ref-picker').value = rv;
    document.getElementById('compare-btn').disabled = false;
  }, { sv: sessionVal, rv: refVal });
  await page.click('#compare-btn');
  await page.waitForFunction(() =>
    document.querySelectorAll('.panel-svg').length > 0, { timeout: 10000 });
}

// Simulate HTML5 drag-and-drop via DragEvent dispatch.
// Panels are non-draggable by default (U1 fix) — we must grip the ⠿ handle
// (mousedown on .drag-handle) before dispatching dragstart, matching real
// browser behaviour.
async function simulateDrag(page, sourceId, targetId) {
  await page.evaluate(({ sourceId, targetId }) => {
    const panels = document.getElementById('panels');
    const src = panels.querySelector(`.panel-wrap[data-panel-id="${sourceId}"]`);
    const tgt = panels.querySelector(`.panel-wrap[data-panel-id="${targetId}"]`);
    if (!src || !tgt) throw new Error(`panels not found: ${sourceId} → ${targetId}`);
    const handle = src.querySelector('.drag-handle');
    if (!handle) throw new Error(`drag handle missing on ${sourceId}`);
    handle.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    const dt = new DataTransfer();
    src.dispatchEvent(new DragEvent('dragstart', { bubbles: true, cancelable: true, dataTransfer: dt }));
    tgt.dispatchEvent(new DragEvent('dragover',  { bubbles: true, cancelable: true, dataTransfer: dt }));
    tgt.dispatchEvent(new DragEvent('drop',      { bubbles: true, cancelable: true, dataTransfer: dt }));
    src.dispatchEvent(new DragEvent('dragend',   { bubbles: true, dataTransfer: dt }));
  }, { sourceId, targetId });
  await page.waitForTimeout(300);
}

// Return ordered panel-id list of rendered panel-wraps
async function getPanelOrder(page) {
  return page.evaluate(() =>
    Array.from(document.querySelectorAll('#panels .panel-wrap[data-panel-id]'))
      .map(el => el.dataset.panelId));
}

// ── Main ──────────────────────────────────────────────────────────────────────
(async () => {
  const { server, port } = await startServer();
  const browser = await chromium.launch();
  const ctx     = await browser.newContext();

  try {
    console.log('\n── F8: ABS / TC full panels ────────────────────────────────');

    // T1: Post-M6 session → ABS and TC panels appear with polylines and midlines
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await loadFiles(page, [SESSION_B]);
      const v0 = await getPickerValue(page, 0);
      const v1 = await getPickerValue(page, 1) ?? v0;
      await compare(page, v0, v1);
      await screenshot(page, 't1-abs-tc-panels');

      const panelIds = await getPanelOrder(page);
      assert(panelIds.includes('abs'), 'T1: ABS panel present in DOM', panelIds.join(','));
      assert(panelIds.includes('tc'),  'T1: TC panel present in DOM',  panelIds.join(','));

      const absPolylines = await page.$$eval(
        'svg.panel-svg[data-panel-id="abs"] polyline', els => els.length);
      const tcPolylines  = await page.$$eval(
        'svg.panel-svg[data-panel-id="tc"]  polyline', els => els.length);
      assert(absPolylines >= 1, 'T1: ABS panel has polyline', `got ${absPolylines}`);
      assert(tcPolylines  >= 1, 'T1: TC panel has polyline',  `got ${tcPolylines}`);

      // Midline: dashed horizontal line at y=0.5
      const absMidlines = await page.$eval(
        'svg.panel-svg[data-panel-id="abs"]',
        svg => svg.querySelectorAll('line[stroke-dasharray="4 4"]').length);
      assert(absMidlines >= 1, 'T1: ABS panel has midline', `got ${absMidlines}`);

      await page.close();
    }

    // T2: Pre-M6 session → ABS/TC panels absent; ≥7 panel SVGs render normally
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await loadFiles(page, [SESSION_A]);
      const v0 = await getPickerValue(page, 0);
      const v1 = await getPickerValue(page, 1) ?? v0;
      await compare(page, v0, v1);
      await screenshot(page, 't2-no-abs-tc');

      const panelIds = await getPanelOrder(page);
      assert(!panelIds.includes('abs'), 'T2: ABS panel absent for pre-M6 session', panelIds.join(','));
      assert(!panelIds.includes('tc'),  'T2: TC panel absent for pre-M6 session',  panelIds.join(','));

      // ≥7 because slip placeholder has no SVG (session may lack slip columns)
      const svgCount = await page.$$eval('.panel-svg', els => els.length);
      assert(svgCount >= 7, 'T2: ≥7 panel SVGs rendered (no ABS/TC)', `got ${svgCount}`);

      const errLogs = consoleLogs.filter(l => l.startsWith('[error]') || l.startsWith('[pageerror]'));
      assert(errLogs.length === 0, 'T2: no console errors', errLogs.join('; ') || 'none');

      await page.close();
    }

    // T3: Zoom over range → ABS panel clips correctly (clip-path attribute present)
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await loadFiles(page, [SESSION_B]);
      const v0 = await getPickerValue(page, 0);
      const v1 = await getPickerValue(page, 1) ?? v0;
      await compare(page, v0, v1);

      // Apply a zoom by dragging on the plot area
      const plotArea = page.locator('#plot-area');
      const pb = await plotArea.boundingBox();
      await plotArea.hover({ position: { x: pb.width * 0.2, y: 30 } });
      await page.mouse.down();
      await plotArea.hover({ position: { x: pb.width * 0.4, y: 30 } });
      await page.mouse.up();
      await page.waitForTimeout(400);

      const absClip = await page.$eval(
        'svg.panel-svg[data-panel-id="abs"] polyline',
        pl => pl.getAttribute('clip-path')
      ).catch(() => null);
      assert(absClip && absClip.includes('clip-abs'),
        'T3: ABS polyline has clip-path after zoom', `got ${absClip}`);

      await screenshot(page, 't3-abs-zoom');
      await page.close();
    }

    console.log('\n── F9: Draggable panel reorder ─────────────────────────────');

    // T4: Drag Δt to top → renders above Speed; cursor and zoom still work
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await loadFiles(page, [SESSION_A]);
      const v0 = await getPickerValue(page, 0);
      const v1 = await getPickerValue(page, 1) ?? v0;
      await compare(page, v0, v1);

      const before = await getPanelOrder(page);
      assert(before[0] !== 'dt', 'T4: dt not at top before drag', `before: ${before.join(',')}`);

      await simulateDrag(page, 'dt', 'speed');
      await page.waitForFunction(() =>
        document.querySelectorAll('.panel-svg').length > 0, { timeout: 5000 });

      const after = await getPanelOrder(page);
      assert(after[0] === 'dt', 'T4: dt is first panel after drag', `after: ${after.join(',')}`);

      // Cursor mousemove should not throw
      const cursorOk = await page.evaluate(() => {
        try {
          const svg = document.querySelector('.panel-svg');
          if (!svg) return false;
          const r = svg.getBoundingClientRect();
          document.getElementById('plot-area').dispatchEvent(new MouseEvent('mousemove', {
            clientX: r.left + r.width / 2, clientY: r.top + 10, bubbles: true,
          }));
          return true;
        } catch { return false; }
      });
      assert(cursorOk, 'T4: cursor mousemove OK after reorder');

      // Double-click zoom reset should not throw
      await page.dblclick('#plot-area');
      await page.waitForTimeout(200);
      const svgsAfter = await page.$$eval('.panel-svg', els => els.length);
      assert(svgsAfter >= 7, 'T4: panels still rendered after zoom reset', `got ${svgsAfter}`);

      await screenshot(page, 't4-drag-dt-top');
      await page.close();
    }

    // T5: Custom order persists across page reload
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      const customOrder = ['dt','speed','throttle','tc','brake','abs','rpm','gear','steering','slip'];
      await page.evaluate(order => {
        localStorage.setItem('lap-telemetry.panel-order.v1', JSON.stringify(order));
      }, customOrder);
      await page.reload();
      await loadFiles(page, [SESSION_A]);
      const v0 = await getPickerValue(page, 0);
      const v1 = await getPickerValue(page, 1) ?? v0;
      await compare(page, v0, v1);

      const rendered = await getPanelOrder(page);
      // dt should be first (abs/tc absent for pre-M6, but order is still loaded)
      assert(rendered[0] === 'dt', 'T5: persisted order restored — dt first on reload',
        `got: ${rendered.join(',')}`);

      await screenshot(page, 't5-order-persisted');
      await page.close();
    }

    // T6: Reset button restores default order; localStorage key cleared
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await page.evaluate(() => {
        localStorage.setItem('lap-telemetry.panel-order.v1',
          JSON.stringify(['dt','speed','throttle','tc','brake','abs','rpm','gear','steering','slip']));
      });
      await page.reload();
      await loadFiles(page, [SESSION_A]);
      const v0 = await getPickerValue(page, 0);
      const v1 = await getPickerValue(page, 1) ?? v0;
      await compare(page, v0, v1);

      await page.click('#order-reset');
      await page.waitForTimeout(400);

      const orderAfter = await getPanelOrder(page);
      assert(orderAfter[0] === 'speed', 'T6: speed is first after reset',
        `got: ${orderAfter.join(',')}`);

      const lsVal = await page.evaluate(() =>
        localStorage.getItem('lap-telemetry.panel-order.v1'));
      assert(lsVal === null, 'T6: localStorage key cleared after reset', `got: ${lsVal}`);

      await screenshot(page, 't6-order-reset');
      await page.close();
    }

    // T7: Load a new lap after reordering → render uses persisted order
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await loadFiles(page, [SESSION_A]);
      const v0 = await getPickerValue(page, 0);
      const v1 = await getPickerValue(page, 1) ?? v0;
      await compare(page, v0, v1);

      await simulateDrag(page, 'dt', 'speed');
      await page.waitForTimeout(300);

      // Re-compare (simulates loading a new lap)
      await page.click('#compare-btn');
      await page.waitForFunction(() =>
        document.querySelectorAll('.panel-svg').length > 0, { timeout: 5000 });

      const order = await getPanelOrder(page);
      assert(order[0] === 'dt', 'T7: reordered layout preserved after re-compare',
        `got: ${order.join(',')}`);

      await page.close();
    }

    console.log('\n── F10: Y-axis legibility ───────────────────────────────────');

    // T8: Δt panel shows 3–5 Y-axis labels with round integer values
    // (use two different laps so Δt has a real, non-zero range)
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await loadFiles(page, [SESSION_A]);
      const v0 = await getPickerValue(page, 1);  // lap 1
      const v1 = await getPickerValue(page, 2);  // lap 2
      await compare(page, v0, v1);
      await screenshot(page, 't8-dt-yticks');

      // x="53" = PAD.left(58) - 5; filters out the "end Δt" readout at x~876
      const dtLabels = await page.$$eval(
        'svg.panel-svg[data-panel-id="dt"] text[text-anchor="end"][font-size="9"]',
        els => els.map(el => el.textContent.trim()));
      const count = dtLabels.length;
      assert(count >= 3 && count <= 5, 'T8: Δt panel has 3–5 Y-axis labels',
        `got ${count}: ${dtLabels.join(', ')}`);

      // Labels should be integers (e.g. +100 ms, -50 ms, 0)
      const allInt = dtLabels.every(l => /^[+-]?\d+$/.test(l.replace(/\s/g, '')));
      assert(allInt, 'T8: Δt Y-axis labels are integers', dtLabels.join(', '));

      await page.close();
    }

    // T9: Slip panel shows 3–5 Y-axis labels (post-M6 session has slip data)
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await loadFiles(page, [SESSION_B]);
      const v0 = await getPickerValue(page, 0);
      const v1 = await getPickerValue(page, 1) ?? v0;
      await compare(page, v0, v1);
      await screenshot(page, 't9-slip-yticks');

      const slipSvg = await page.$('svg.panel-svg[data-panel-id="slip"]');
      if (!slipSvg) {
        assert(false, 'T9: slip panel SVG present', 'not found — no slip data in session');
      } else {
        const labels = await page.$$eval(
          'svg.panel-svg[data-panel-id="slip"] text[text-anchor="end"][font-size="9"]',
          els => els.map(el => el.textContent.trim()));
        const count = labels.length;
        assert(count >= 3 && count <= 5, 'T9: slip panel has 3–5 Y-axis labels',
          `got ${count}: ${labels.join(', ')}`);
      }
      await page.close();
    }

    // T10: Zoom into small distance range → Δt tick count stays in 3–5
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await loadFiles(page, [SESSION_A]);
      const v0 = await getPickerValue(page, 1);
      const v1 = await getPickerValue(page, 2);
      await compare(page, v0, v1);

      const plotArea = page.locator('#plot-area');
      const pb = await plotArea.boundingBox();
      await plotArea.hover({ position: { x: pb.width * 0.3, y: 50 } });
      await page.mouse.down();
      await plotArea.hover({ position: { x: pb.width * 0.35, y: 50 } });
      await page.mouse.up();
      await page.waitForTimeout(400);
      await screenshot(page, 't10-zoomed-dt-yticks');

      const labels = await page.$$eval(
        'svg.panel-svg[data-panel-id="dt"] text[text-anchor="end"][font-size="9"]',
        els => els.map(el => el.textContent.trim()));
      const count = labels.length;
      assert(count >= 3 && count <= 5, 'T10: Δt panel has 3–5 labels after zoom',
        `got ${count}: ${labels.join(', ')}`);

      await page.close();
    }

    console.log('\n── F11: Gear panel height ×1.3 ─────────────────────────────');

    // T11: Gear panel viewBox height = Math.round(60 * 1.3) = 78
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await loadFiles(page, [SESSION_A]);
      const v0 = await getPickerValue(page, 1);
      const v1 = await getPickerValue(page, 2);
      await compare(page, v0, v1);
      await screenshot(page, 't11-gear-height');

      const viewBox = await page.$eval(
        'svg.panel-svg[data-panel-id="gear"]', svg => svg.getAttribute('viewBox'));
      assert(viewBox === '0 0 900 78', 'T11: gear panel viewBox height = 78', `got "${viewBox}"`);

      await page.close();
    }

    // T12: Gear Y-axis spans at least 5 gear steps
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await loadFiles(page, [SESSION_A]);
      const v0 = await getPickerValue(page, 1);
      const v1 = await getPickerValue(page, 2);
      await compare(page, v0, v1);

      const gearLabels = await page.$$eval(
        'svg.panel-svg[data-panel-id="gear"] text[text-anchor="end"]',
        els => els.map(el => parseFloat(el.textContent)).filter(isFinite));
      const mn = Math.min(...gearLabels), mx = Math.max(...gearLabels);
      assert(mx - mn >= 5, 'T12: gear Y-axis spans ≥5 gear steps', `range ${mn}–${mx}`);

      await page.close();
    }

    // T13: Gear trace clips correctly after zoom; tooltip shows on hover
    {
      const page = await ctx.newPage();
      setupPageLogging(page);
      await page.goto(`http://127.0.0.1:${port}`);
      await loadFiles(page, [SESSION_A]);
      const v0 = await getPickerValue(page, 1);
      const v1 = await getPickerValue(page, 2);
      await compare(page, v0, v1);

      const plotArea = page.locator('#plot-area');
      const pb = await plotArea.boundingBox();
      await plotArea.hover({ position: { x: pb.width * 0.2, y: 50 } });
      await page.mouse.down();
      await plotArea.hover({ position: { x: pb.width * 0.3, y: 50 } });
      await page.mouse.up();
      await page.waitForTimeout(400);

      const gearClip = await page.$eval(
        'svg.panel-svg[data-panel-id="gear"] polyline',
        pl => pl.getAttribute('clip-path')
      ).catch(() => null);
      assert(gearClip && gearClip.includes('clip-gear'),
        'T13: gear polyline has clip-path after zoom', `got ${gearClip}`);

      // Gear panel can be below the default viewport — use locator.hover()
      // with element-relative coordinates so Playwright scrolls it into view.
      const gearSvg = page.locator('svg.panel-svg[data-panel-id="gear"]');
      const gearBox = await gearSvg.boundingBox();
      await gearSvg.hover({ position: { x: gearBox.width * 0.5, y: gearBox.height * 0.5 } });
      await page.waitForTimeout(150);
      const tooltipVisible = await page.$eval('#tooltip', el => el.style.display !== 'none');
      assert(tooltipVisible, 'T13: tooltip visible on hover after zoom');

      await screenshot(page, 't13-gear-zoom');
      await page.close();
    }

    // Console errors across all tests
    const errors = consoleLogs.filter(l => l.startsWith('[error]') || l.startsWith('[pageerror]'));
    assert(errors.length === 0, 'Console: no browser errors', errors.join('; ') || 'none');

  } finally {
    await browser.close();
    server.close();
  }

  // ── Report ────────────────────────────────────────────────────────────────
  const passed = results.filter(r => r.status === 'PASS').length;
  const total  = results.length;
  console.log(`\n${'═'.repeat(35)}`);
  console.log(`  ${passed}/${total} assertions passed`);
  if (failCount === 0) {
    console.log('  ✔ All assertions passed');
  } else {
    console.log(`  ✖ ${failCount} FAILURE${failCount > 1 ? 'S' : ''}`);
    results.filter(r => r.status === 'FAIL').forEach(r =>
      console.log(`    FAIL: ${r.name}${r.detail ? ' [' + r.detail + ']' : ''}`));
  }
  console.log(`${'═'.repeat(35)}\n`);

  fs.writeFileSync(path.join(REPORT_DIR, 'REPORT.md'), [
    '# F8–F11 Test Report',
    '',
    `**${passed}/${total} passed** · ${failCount === 0 ? '✅ All green' : `❌ ${failCount} failed`}`,
    '',
    '## Results',
    '',
    ...results.map(r => `- [${r.status}] ${r.name}${r.detail ? ' — ' + r.detail : ''}`),
  ].join('\n'));

  process.exit(failCount > 0 ? 1 : 0);
})();
