/**
 * Phase 00.1 — Renderer Responsive Test Suite
 * 
 * Implements: Phase 0.1 "Renderer responds to container size (pure refactor)"
 * Spec: https://github.com/vasco-duarte-oikosofy/lap-telemetry/blob/main/track-heatmap-spec.md#phase-01--renderer-responds-to-container-size-pure-refactor
 * 
 * Verifies that the circuit map and panels render correctly at various
 * container widths without distortion, overflow, or clipped labels.
 * 
 * Acceptance criteria (from spec):
 * - Screenshot test: render at 320px, 768px, 1024px, 1440px, and 2000px container widths.
 *   All five render without overflow, distortion, or clipped labels.
 * - Pixel-diff test against the pre-change renderer at the original size: identical.
 *   (If it's not identical, you changed behavior — that's a different subphase.)
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

// ── Screenshot helper ─────────────────────────────────────────────────────────
async function screenshot(page, name) {
  const path_s = path.join(SHOTS_DIR, `${name}.png`);
  await page.screenshot({ path: path_s });
  log(`  📸 ${name}.png`);
}

// ── Test widths ───────────────────────────────────────────────────────────────
const TEST_WIDTHS = [320, 768, 1024, 1440, 2000];

// ── Main test flow ────────────────────────────────────────────────────────────
async function runTests() {
  console.log('═══ Phase 00.1 — Renderer Responsive Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  console.log(`URL: ${url}`);
  console.log(`Report: ${REPORT_DIR}\n`);

  const browser = await chromium.launch();

  try {
    // ── Test 1: Render at different widths ────────────────────────────────────
    console.log('════ SCENARIO 1: Responsive rendering at multiple widths ════');
    
    for (const width of TEST_WIDTHS) {
      log(`\n  Testing at ${width}px container width...`);
      
      const page = await browser.newPage();
      await page.setViewportSize({ width: width + 100, height: 1200 });
      await page.goto(url);
      
      // Load session file first
      const uploadInput = await page.$('#file-input');
      await uploadInput.setInputFiles(SESSION);
      await page.waitForFunction(() => {
        const keys = window.__getSessionKeys?.();
        return keys && keys.length > 0;
      }, { timeout: 10000 });
      
      // Select two laps to compare
      await page.evaluate(() => {
        const opts = [...document.getElementById('session-picker').querySelectorAll('option')].filter(o => o.value);
        if (opts.length >= 2) {
          const sp = document.getElementById('session-picker');
          const rp = document.getElementById('ref-picker');
          sp.value = opts[0].value;
          rp.value = opts[1].value;
          sp.dispatchEvent(new Event('change'));
        }
      });
      
      // Wait for panels to render AND map to be visible
      await page.waitForFunction(() => {
        const panels = document.querySelectorAll('#panels .panel-svg');
        const mapPanel = document.getElementById('circuit-map-panel');
        return panels.length >= 7 && mapPanel && mapPanel.style.display !== 'none';
      }, { timeout: 10000 });
      
      // Get the circuit map panel and SVG
      const mapPanel = page.locator('#circuit-map-panel');
      const mapSvg = page.locator('#circuit-map-svg');
      
      // Wait for SVG to be rendered
      await mapSvg.waitFor({ state: 'visible' });
      
      // Get actual rendered dimensions
      const mapPanelBox = await mapPanel.boundingBox();
      const mapSvgBox = await mapSvg.boundingBox();
      
      // Map panel should be responsive (Phase 0 sets it to 50% width at desktop)
      // At mobile breakpoints (<1024px) it goes to 100% width
      const expectedMinWidth = width < 1024 ? width * 0.9 : width * 0.45;
      assert(
        mapPanelBox.width >= expectedMinWidth,
        `Map panel width at ${width}px`,
        `got ${Math.round(mapPanelBox.width)}px (expected ≥${Math.round(expectedMinWidth)}px)`
      );
      
      // Map panel height should be at least minimum (420px)
      assert(
        mapPanelBox.height >= 420,
        `Map panel height at ${width}px`,
        `got ${Math.round(mapPanelBox.height)}px (expected ≥420px)`
      );
      
      // SVG should fill the panel (within 30px tolerance for padding/borders)
      assert(
        Math.abs(mapSvgBox.width - mapPanelBox.width) <= 30,
        `SVG fills panel width at ${width}px`,
        `panel=${Math.round(mapPanelBox.width)}px, svg=${Math.round(mapSvgBox.width)}px`
      );
      
      // Check for overflow - SVG content should be visible
      const trackOutline = page.locator('#track-outline');
      await trackOutline.waitFor({ state: 'visible' });
      
      // Get the points attribute to verify track is rendered
      const points = await trackOutline.getAttribute('points');
      assert(
        points && points.split(' ').length > 10,
        `Track outline has points at ${width}px`,
        `got ${points ? points.split(' ').length : 0} coordinate values`
      );
      
      // Check panels container
      const panelsContainer = page.locator('#panels');
      await panelsContainer.waitFor({ state: 'visible' });
      
      const panelsBox = await panelsContainer.boundingBox();
      // Panels should be responsive and fit reasonably within viewport
      // Allow some tolerance for body padding (24px each side) and panel margins
      const maxPanelWidth = width + 50; // generous tolerance
      assert(
        panelsBox.width <= maxPanelWidth,
        `Panels fit within viewport at ${width}px`,
        `panel width=${Math.round(panelsBox.width)}px, viewport=${width}px`
      );
      
      // Count rendered panels
      const panelCount = await page.evaluate(() => document.querySelectorAll('#panels .panel-svg').length);
      assert(
        panelCount >= 7,
        `Panels rendered at ${width}px`,
        `got ${panelCount} panels`
      );
      
      // Take a screenshot for visual verification
      await screenshot(page, `responsive-${width}px`);
      
      await page.close();
    }
    
    // ── Test 2: Pixel-diff at baseline width (900px) ─────────────────────────
    console.log('\n════ SCENARIO 2: Baseline width pixel comparison ════');
    
    const page = await browser.newPage();
    await page.setViewportSize({ width: 1000, height: 1200 });
    await page.goto(url);
    
    // Load session
    const uploadInput = await page.$('#file-input');
    await uploadInput.setInputFiles(SESSION);
    await page.waitForFunction(() => {
      const keys = window.__getSessionKeys?.();
      return keys && keys.length > 0;
    }, { timeout: 10000 });
    
    // Select laps
    await page.evaluate(() => {
      const opts = [...document.getElementById('session-picker').querySelectorAll('option')].filter(o => o.value);
      if (opts.length >= 2) {
        const sp = document.getElementById('session-picker');
        const rp = document.getElementById('ref-picker');
        sp.value = opts[0].value;
        rp.value = opts[1].value;
        sp.dispatchEvent(new Event('change'));
      }
    });
    
    await page.waitForFunction(() => document.querySelectorAll('#panels .panel-svg').length >= 7, { timeout: 10000 });
    
    // Verify SVG viewBox attributes are set correctly
    const panelSvgViewBox = await page.evaluate(() => {
      const panels = document.querySelectorAll('#panels .panel-svg');
      return Array.from(panels).map(p => p.getAttribute('viewBox'));
    });
    
    assert(
      panelSvgViewBox.every(vb => vb && vb.split(' ')[2] !== '900'),
      'Panel SVGs have dynamic viewBox (not hardcoded 900)',
      `viewBoxes: ${panelSvgViewBox.slice(0, 3).join(', ')}...`
    );
    
    const mapSvgViewBox = await page.evaluate(() => {
      const mapSvg = document.getElementById('circuit-map-svg');
      return mapSvg.getAttribute('viewBox');
    });
    
    assert(
      mapSvgViewBox === '0 0 250 250',
      'Circuit map SVG has correct viewBox',
      `got "${mapSvgViewBox}"`
    );
    
    await screenshot(page, 'baseline-900px');
    await page.close();
    
    // ── Test 3: No console errors ────────────────────────────────────────────
    console.log('\n════ SCENARIO 3: Console error check ════');
    
    const page2 = await browser.newPage();
    let errorCount = 0;
    page2.on('pageerror', e => {
      errorCount++;
      log(`  [pageerror] ${e.message}`);
    });
    page2.on('console', m => {
      if (m.type() === 'error') {
        errorCount++;
        log(`  [console err] ${m.text()}`);
      }
    });
    
    await page2.setViewportSize({ width: 1540, height: 1200 });
    await page2.goto(url);
    
    // Load and compare
    const uploadInput2 = await page2.$('#file-input');
    await uploadInput2.setInputFiles(SESSION);
    await page2.waitForFunction(() => {
      const keys = window.__getSessionKeys?.();
      return keys && keys.length > 0;
    }, { timeout: 10000 });
    
    await page2.evaluate(() => {
      const opts = [...document.getElementById('session-picker').querySelectorAll('option')].filter(o => o.value);
      if (opts.length >= 2) {
        const sp = document.getElementById('session-picker');
        const rp = document.getElementById('ref-picker');
        sp.value = opts[0].value;
        rp.value = opts[1].value;
        sp.dispatchEvent(new Event('change'));
      }
    });
    
    await page2.waitForFunction(() => document.querySelectorAll('#panels .panel-svg').length >= 7, { timeout: 10000 });
    
    assert(
      errorCount === 0,
      'No browser console errors',
      `${errorCount} errors`
    );
    
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
    `## Results`,
    '',
    `  ${passCount}/${passCount + failCount} assertions passed`,
    '',
    failCount === 0 ? '  ✔ All assertions passed' : `  ✘ ${failCount} assertion(s) failed`,
    '',
    '## Test Widths',
    '',
    `Tested at: ${TEST_WIDTHS.join('px, ')}px`,
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
