/**
 * Phase 00.1 — Renderer Responsive Test Suite
 *
 * Implements: Phase 0.1 "Renderer responds to container size (pure refactor)".
 *
 * Verifies that the circuit map and panels render correctly at explicit content
 * widths without horizontal overflow, distortion, or missing rendered data.
 * Screenshots are written as artifacts; layout and render invariants below are
 * the automated assertions.
 *
 * Run: node scripts/test_001_responsive.js
 *
 * Produces 001-test-report/ with screenshots and REPORT.md.
 */

'use strict';

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { startServer } = require('./lib/test-server');

// ── Paths ─────────────────────────────────────────────────────────────────────
const ROOT         = path.resolve(__dirname, '..');
const WEB_DIR      = path.join(ROOT, 'web');
const SESSIONS_DIR = path.join(ROOT, 'sessions');
const REPORT_DIR   = path.join(ROOT, '001-test-report');
const SHOTS_DIR    = path.join(REPORT_DIR, 'screenshots');

const SESSION = path.join(SESSIONS_DIR, 'session_20260510T074144Z_circuit-de-barcelona_lmu.parquet');

fs.mkdirSync(SHOTS_DIR, { recursive: true });

// ── Test utilities ────────────────────────────────────────────────────────────
const results = [];
let passCount = 0, failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failCount++; else passCount++;
  results.push({ status, name, detail });
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function log(msg) {
  console.log(msg);
}

function setupPageLogging(page, label) {
  const errors = [];
  page.on('pageerror', e => {
    const line = `${label}: pageerror: ${e.message}`;
    errors.push(line);
    log(`  [pageerror] ${line}`);
  });
  page.on('console', m => {
    if (m.type() === 'error') {
      const line = `${label}: console error: ${m.text()}`;
      errors.push(line);
      log(`  [console err] ${line}`);
    }
  });
  return errors;
}

async function screenshot(page, name) {
  const path_s = path.join(SHOTS_DIR, `${name}.png`);
  await page.screenshot({ path: path_s });
  const size = fs.existsSync(path_s) ? fs.statSync(path_s).size : 0;
  assert(size > 0, `Screenshot artifact written: ${name}.png`, `${size} bytes`);
  log(`  📸 ${name}.png`);
}

async function loadAndCompare(page) {
  await page.locator('#file-input').setInputFiles(SESSION);
  await page.waitForFunction(() => window.__getSessionKeys?.().length > 0, { timeout: 10000 });

  await page.evaluate(() => {
    const opts = [...document.getElementById('session-picker').querySelectorAll('option')]
      .filter(o => o.value);
    if (opts.length < 2) return;
    const sp = document.getElementById('session-picker');
    const rp = document.getElementById('ref-picker');
    sp.value = opts[0].value;
    rp.value = opts[1].value;
    sp.dispatchEvent(new Event('change'));
    rp.dispatchEvent(new Event('change'));
  });

  await page.evaluate(() => {
    const mode = document.getElementById('map-mode');
    if (mode) {
      mode.value = 'outline';
      mode.dispatchEvent(new Event('change'));
    }
  });

  await page.waitForFunction(() => {
    const keys = window.__getSessionKeys?.() || [];
    const panels = document.querySelectorAll('#panels .panel-svg');
    const speedLines = document.querySelectorAll('svg[data-panel-id="speed"] polyline');
    const dtLines = document.querySelectorAll('svg[data-panel-id="dt"] polyline');
    const trackPoints = document.getElementById('track-outline')?.getAttribute('points') || '';
    return keys.length > 0 &&
      panels.length >= 7 &&
      speedLines.length >= 1 &&
      dtLines.length >= 1 &&
      trackPoints.split(' ').length > 10;
  }, { timeout: 10000 });
}

// ── Test widths ───────────────────────────────────────────────────────────────
const TEST_WIDTHS = [320, 768, 1024, 1440, 2000];

// ── Main test flow ────────────────────────────────────────────────────────────
async function runTests() {
  console.log('═══ Phase 00.1 — Renderer Responsive Test Suite ═══\n');
  assert(fs.existsSync(SESSION), 'Fixture parquet exists', SESSION);
  if (!fs.existsSync(SESSION)) process.exit(1);

  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  console.log(`URL: ${url}`);
  console.log(`Report: ${REPORT_DIR}\n`);

  const browser = await chromium.launch();

  try {
    // ── Test 1: Render at explicit content widths ─────────────────────────────
    console.log('════ SCENARIO 1: Responsive rendering at multiple content widths ════');

    for (const width of TEST_WIDTHS) {
      log(`\n  Testing at ${width}px content width...`);

      const page = await browser.newPage();
      const errors = setupPageLogging(page, `responsive-${width}`);
      await page.goto(url);

      const bodyPadding = await page.evaluate(() => {
        const cs = getComputedStyle(document.body);
        return parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
      });
      await page.setViewportSize({ width: Math.round(width + bodyPadding), height: 1200 });
      await loadAndCompare(page);

      const layout = await page.evaluate(() => {
        const bodyStyle = getComputedStyle(document.body);
        const paddingX = parseFloat(bodyStyle.paddingLeft) + parseFloat(bodyStyle.paddingRight);
        const map = document.getElementById('circuit-map-panel').getBoundingClientRect();
        const mapSvg = document.getElementById('circuit-map-svg').getBoundingClientRect();
        const mapCanvas = document.getElementById('track-heatmap-canvas').getBoundingClientRect();
        const panels = document.getElementById('panels').getBoundingClientRect();
        const plot = document.getElementById('plot-area').getBoundingClientRect();
        const panelSvgs = [...document.querySelectorAll('#panels .panel-svg')].map(svg => {
          const r = svg.getBoundingClientRect();
          return { left: r.left, right: r.right, width: r.width };
        });
        return {
          contentWidth: window.innerWidth - paddingX,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          map: { width: map.width, height: map.height, left: map.left, right: map.right },
          mapRenderer: {
            width: Math.max(mapSvg.width, mapCanvas.width),
            height: Math.max(mapSvg.height, mapCanvas.height),
          },
          panels: { width: panels.width, left: panels.left, right: panels.right },
          plot: { width: plot.width, left: plot.left, right: plot.right },
          panelSvgs,
        };
      });

      assert(
        Math.abs(layout.contentWidth - width) <= 2,
        `Explicit content width at ${width}px`,
        `content=${Math.round(layout.contentWidth)}px viewport=${layout.clientWidth}px`
      );

      const expectedMinWidth = width < 1024 ? width * 0.9 : width * 0.45;
      assert(
        layout.map.width >= expectedMinWidth,
        `Map panel width at ${width}px`,
        `got ${Math.round(layout.map.width)}px (expected ≥${Math.round(expectedMinWidth)}px)`
      );

      assert(
        layout.map.height >= 420,
        `Map panel height at ${width}px`,
        `got ${Math.round(layout.map.height)}px (expected ≥420px)`
      );

      assert(
        Math.abs(layout.mapRenderer.width - layout.map.width) <= 30,
        `Visible map renderer fills panel width at ${width}px`,
        `panel=${Math.round(layout.map.width)}px, renderer=${Math.round(layout.mapRenderer.width)}px`
      );

      const points = await page.locator('#track-outline').getAttribute('points');
      assert(
        points && points.split(' ').length > 10,
        `Track outline has points at ${width}px`,
        `got ${points ? points.split(' ').length : 0} coordinate values`
      );

      const rendererRight = Math.max(layout.map.right, layout.plot.right, layout.panels.right);
      const rendererOverflowPx = rendererRight - layout.clientWidth;
      const documentOverflowPx = layout.scrollWidth - layout.clientWidth;
      assert(
        rendererOverflowPx <= 1,
        `Responsive renderer stays inside viewport at ${width}px`,
        `rendererRight=${Math.round(rendererRight)}px clientWidth=${layout.clientWidth}px documentOverflow=${documentOverflowPx}px`
      );

      const panelBoundsOk = layout.panelSvgs.every(r =>
        r.left >= layout.plot.left - 1 && r.right <= layout.plot.right + 1 && r.width <= layout.plot.width + 1
      );
      assert(
        panelBoundsOk,
        `Panel SVGs stay inside plot area at ${width}px`,
        `plot=${Math.round(layout.plot.width)}px panels=${layout.panelSvgs.map(r => Math.round(r.width)).join(',')}`
      );

      const panelCount = await page.locator('#panels .panel-svg').count();
      assert(panelCount >= 7, `Panels rendered at ${width}px`, `got ${panelCount} panels`);

      assert(errors.length === 0, `No browser console errors at ${width}px`, errors.join('; ') || 'none');
      await screenshot(page, `responsive-${width}px`);
      await page.close();
    }

    // ── Test 2: Baseline structural consistency at original-ish width ────────
    console.log('\n════ SCENARIO 2: Baseline structural consistency ════');

    const page = await browser.newPage();
    const baselineErrors = setupPageLogging(page, 'baseline');
    await page.setViewportSize({ width: 1000, height: 1200 });
    await page.goto(url);
    await loadAndCompare(page);

    const panelSvgMetrics = await page.evaluate(() => {
      return [...document.querySelectorAll('#panels .panel-svg')].map(svg => {
        const viewBox = svg.getAttribute('viewBox') || '';
        const parts = viewBox.split(/\s+/).map(Number);
        const rect = svg.getBoundingClientRect();
        return { viewBox, viewBoxWidth: parts[2], renderedWidth: rect.width };
      });
    });

    const viewBoxesMatchRenderWidth = panelSvgMetrics.every(m =>
      Number.isFinite(m.viewBoxWidth) && Math.abs(m.viewBoxWidth - m.renderedWidth) <= 2
    );
    assert(
      viewBoxesMatchRenderWidth,
      'Panel SVG viewBox widths match rendered widths',
      panelSvgMetrics.slice(0, 3).map(m => `${m.viewBoxWidth}/${Math.round(m.renderedWidth)}`).join(', ')
    );

    const mapSvgViewBox = await page.locator('#circuit-map-svg').getAttribute('viewBox');
    assert(mapSvgViewBox === '0 0 250 250', 'Circuit map SVG has correct viewBox', `got "${mapSvgViewBox}"`);
    assert(baselineErrors.length === 0, 'No browser console errors in baseline scenario', baselineErrors.join('; ') || 'none');

    await screenshot(page, 'baseline-900px');
    await page.close();

    // ── Test 3: Full render console error check ──────────────────────────────
    console.log('\n════ SCENARIO 3: Console error check ════');

    const page2 = await browser.newPage();
    const finalErrors = setupPageLogging(page2, 'console-check');
    await page2.setViewportSize({ width: 1540, height: 1200 });
    await page2.goto(url);
    await loadAndCompare(page2);

    assert(finalErrors.length === 0, 'No browser console errors', finalErrors.join('; ') || 'none');
    await page2.close();

  } catch (err) {
    console.error('Test execution error:', err);
    failCount++;
    results.push({ status: 'FAIL', name: 'Test execution', detail: err.message });
  } finally {
    await browser.close();
    server.close();
  }

  // ── Write report ────────────────────────────────────────────────────────────
  const report = [
    '# Phase 00.1 — Responsive Renderer Test Report',
    '',
    `**Date:** ${new Date().toISOString()}`,
    `**URL:** http://127.0.0.1:${port}`,
    '',
    '## Results',
    '',
    `  ${passCount}/${passCount + failCount} assertions passed`,
    '',
    failCount === 0 ? '  ✔ All assertions passed' : `  ✘ ${failCount} assertion(s) failed`,
    '',
    '## Test Widths',
    '',
    `Tested content widths: ${TEST_WIDTHS.join('px, ')}px`,
    '',
    '## Screenshot Artifacts',
    '',
    'Screenshots are saved for manual review. Automated assertions above verify layout invariants.',
    '',
    '## Detailed Results',
    '',
    ...results.map(r => `- [${r.status}] ${r.name}${r.detail ? ': ' + r.detail : ''}`),
    '',
  ].join('\n');

  fs.writeFileSync(path.join(REPORT_DIR, 'REPORT.md'), report);

  console.log('\n═══════════════════════════════════');
  console.log(`  ${passCount}/${passCount + failCount} assertions passed`);
  if (failCount === 0) {
    console.log('  ✔ All assertions passed');
  } else {
    console.log(`  ✘ ${failCount} assertion(s) failed`);
  }
  console.log(`  Report: ${REPORT_DIR}`);
  console.log('═══════════════════════════════════\n');

  process.exit(failCount > 0 ? 1 : 0);
}

runTests();
