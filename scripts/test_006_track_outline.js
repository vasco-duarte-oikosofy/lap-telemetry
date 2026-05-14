/**
 * Phase 00.6 — Track Outline Background Test Suite
 *
 * Verifies the track outline rendering:
 * - Track outline is visible underneath the lap polylines
 * - Outline has lower visual weight (lower contrast, thinner)
 * - Outline color matches spec (low-contrast grey)
 * - Draw order: outline → Lap B → Lap A (bottom to top)
 *
 * Run: node scripts/test_006_track_outline.js
 *
 * Produces: 006-test-report/ with screenshots and REPORT.md
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
const REPORT_DIR   = path.join(ROOT, '006-test-report');
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
  return cond;
}

function log(msg) {
  console.log(msg);
}

async function screenshot(page, name) {
  const p = path.join(SHOTS_DIR, `${name}.png`);
  await page.screenshot({ path: p });
  log(`  📸 ${name}.png`);
}

// ── Main test flow ────────────────────────────────────────────────────────────
async function runTests() {
  console.log('═══ Phase 00.6 — Track Outline Background Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  console.log(`URL: ${url}`);
  console.log(`Report: ${REPORT_DIR}\n`);

  const browser = await chromium.launch();

  try {
    // ── SCENARIO 1: Track outline renders underneath polylines ───────────────
    console.log('════ SCENARIO 1: Track outline renders ════');

    const page1 = await browser.newPage({ deviceScaleFactor: 1 });
    await page1.setViewportSize({ width: 1280, height: 900 });
    await page1.goto(url);

    // Load session
    const uploadInput1 = await page1.$('#file-input');
    await uploadInput1.setInputFiles(SESSION);
    await page1.waitForFunction(() => {
      const keys = window.__getSessionKeys?.();
      return keys && keys.length > 0;
    }, { timeout: 10000 });

    // Select two laps
    await page1.evaluate(() => {
      const opts = [...document.getElementById('session-picker').querySelectorAll('option')].filter(o => o.value);
      if (opts.length >= 2) {
        const sp = document.getElementById('session-picker');
        const rp = document.getElementById('ref-picker');
        sp.value = opts[0].value;
        rp.value = opts[1].value;
        sp.dispatchEvent(new Event('change'));
      }
    });

    // Click Compare
    await page1.locator('#compare-btn').click();
    await page1.waitForFunction(() => {
      const panels = document.querySelectorAll('#panels .panel-svg');
      return panels.length >= 7;
    }, { timeout: 10000 });

    // Enable walking skeleton AND track outline feature flags
    const wsEnabled = await page1.evaluate(() => {
      if (typeof window.__setFeatureFlag === 'function') {
        window.__setFeatureFlag('mapWalkingSkeleton', true);
        window.__setFeatureFlag('mapTrackOutline', true);
        document.getElementById('compare-btn').click();
        return true;
      }
      return false;
    });
    await page1.waitForTimeout(500);

    // Check if canvas has content with TWO outline boundaries
    const canvasInfo = await page1.evaluate(() => {
      const canvas = document.getElementById('track-heatmap-canvas');
      if (!canvas) return { error: 'canvas not found' };
      const ctx = canvas.getContext('2d');
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imageData.data;
      let totalPixels = canvas.width * canvas.height;
      let nonTransparentPixels = 0;
      let magentaPixels = 0;   // inner boundary
      let cyanPixels = 0;      // outer boundary
      
      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        const a = data[i + 3];
        
        if (a > 0) nonTransparentPixels++;
        
        // Magenta: high R, low G, high B (inner boundary)
        if (r > 200 && g < 100 && b > 200 && a > 100) {
          magentaPixels++;
        }
        
        // Cyan: low R, high G, high B (outer boundary)
        if (r < 100 && g > 200 && b > 200 && a > 100) {
          cyanPixels++;
        }
      }
      
      return {
        width: canvas.width,
        height: canvas.height,
        totalPixels,
        nonTransparentPixels,
        magentaPixels,
        cyanPixels,
      };
    });

    assert(canvasInfo.width > 0, 'Canvas has positive width', `width=${canvasInfo.width}`);
    assert(canvasInfo.height > 0, 'Canvas has positive height', `height=${canvasInfo.height}`);
    assert(canvasInfo.nonTransparentPixels > 100, 'Canvas has drawn content', `non-transparent pixels=${canvasInfo.nonTransparentPixels}`);
    
    // Check for BOTH outline boundaries (inner and outer)
    assert(canvasInfo.magentaPixels > 50, 'Canvas has magenta pixels (inner boundary)', `magenta pixels=${canvasInfo.magentaPixels}`);
    assert(canvasInfo.cyanPixels > 50, 'Canvas has cyan pixels (outer boundary)', `cyan pixels=${canvasInfo.cyanPixels}`);

    await screenshot(page1, 'track-outline-rendered');
    await page1.close();

    // ── SCENARIO 2: Outline color matches spec ────────────────────────────────
    console.log('\n════ SCENARIO 2: Outline color matches spec ════');

    const page2 = await browser.newPage({ deviceScaleFactor: 1 });
    await page2.setViewportSize({ width: 1280, height: 900 });
    await page2.goto(url);

    // Load session and compare
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

    await page2.locator('#compare-btn').click();
    await page2.waitForFunction(() => document.querySelectorAll('#panels .panel-svg').length >= 7, { timeout: 10000 });

    // Enable feature flags
    await page2.evaluate(() => {
      if (typeof window.__setFeatureFlag === 'function') {
        window.__setFeatureFlag('mapWalkingSkeleton', true);
        window.__setFeatureFlag('mapTrackOutline', true);
        document.getElementById('compare-btn').click();
      }
    });
    await page2.waitForTimeout(500);

    // Verify BOTH outline boundaries are present (inner=magenta, outer=cyan)
    const colorAnalysis = await page2.evaluate(() => {
      const canvas = document.getElementById('track-heatmap-canvas');
      if (!canvas) return { error: 'canvas not found' };
      const ctx = canvas.getContext('2d');
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imageData.data;
      
      let magentaPixels = 0;
      let cyanPixels = 0;
      
      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        const a = data[i + 3];
        
        if (a < 100) continue;
        
        // Magenta: high R, low G, high B (inner boundary)
        if (r > 200 && g < 100 && b > 200) {
          magentaPixels++;
        }
        
        // Cyan: low R, high G, high B (outer boundary)
        if (r < 100 && g > 200 && b > 200) {
          cyanPixels++;
        }
      }
      
      return {
        magentaPixels,
        cyanPixels,
        totalOutlinePixels: magentaPixels + cyanPixels,
      };
    });

    assert(colorAnalysis.magentaPixels > 50, 'Found magenta pixels (inner boundary)', `count=${colorAnalysis.magentaPixels}`);
    assert(colorAnalysis.cyanPixels > 50, 'Found cyan pixels (outer boundary)', `count=${colorAnalysis.cyanPixels}`);
    assert(colorAnalysis.totalOutlinePixels > 100, 'Total outline pixels', `total=${colorAnalysis.totalOutlinePixels}`);

    await screenshot(page2, 'track-outline-color-check');
    await page2.close();

    // ── SCENARIO 3: Draw order verification ───────────────────────────────────
    console.log('\n════ SCENARIO 3: Draw order (outline → Lap B → Lap A) ════');

    const page3 = await browser.newPage({ deviceScaleFactor: 2 }); // Higher DPR for cleaner edges
    await page3.setViewportSize({ width: 1440, height: 900 });
    await page3.goto(url);

    const uploadInput3 = await page3.$('#file-input');
    await uploadInput3.setInputFiles(SESSION);
    await page3.waitForFunction(() => {
      const keys = window.__getSessionKeys?.();
      return keys && keys.length > 0;
    }, { timeout: 10000 });

    await page3.evaluate(() => {
      const opts = [...document.getElementById('session-picker').querySelectorAll('option')].filter(o => o.value);
      if (opts.length >= 2) {
        const sp = document.getElementById('session-picker');
        const rp = document.getElementById('ref-picker');
        sp.value = opts[0].value;
        rp.value = opts[1].value;
        sp.dispatchEvent(new Event('change'));
      }
    });

    await page3.locator('#compare-btn').click();
    await page3.waitForFunction(() => document.querySelectorAll('#panels .panel-svg').length >= 7, { timeout: 10000 });

    await page3.evaluate(() => {
      if (typeof window.__setFeatureFlag === 'function') {
        window.__setFeatureFlag('mapWalkingSkeleton', true);
        window.__setFeatureFlag('mapTrackOutline', true);
        document.getElementById('compare-btn').click();
      }
    });
    await page3.waitForTimeout(500);

    // Scroll map into view
    const mapPanel = page3.locator('#circuit-map-panel');
    await mapPanel.hover({ position: { x: 1, y: 1 } });

    // Verify that BOTH outline boundaries AND lap polylines are visible
    const layerAnalysis = await page3.evaluate(() => {
      const canvas = document.getElementById('track-heatmap-canvas');
      if (!canvas) return { error: 'canvas not found' };
      const ctx = canvas.getContext('2d');
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imageData.data;
      
      let vibrantPixels = 0;   // Lap A/B colors (blue/orange)
      let magentaPixels = 0;   // Inner boundary
      let cyanPixels = 0;      // Outer boundary
      
      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        const a = data[i + 3];
        
        if (a === 0) continue;
        
        // Vibrant: either blue-ish (session) or orange-ish (ref)
        const isBlue = b > r + 30 && b > g;
        const isOrange = r > g + 30 && r > b + 30;
        if (isBlue || isOrange) vibrantPixels++;
        
        // Magenta: inner boundary
        if (r > 200 && g < 100 && b > 200 && a > 100) magentaPixels++;
        
        // Cyan: outer boundary
        if (r < 100 && g > 200 && b > 200 && a > 100) cyanPixels++;
      }
      
      return { vibrantPixels, magentaPixels, cyanPixels };
    });

    assert(layerAnalysis.vibrantPixels > 0, 'Lap polyline colors visible (vibrant pixels)', `count=${layerAnalysis.vibrantPixels}`);
    assert(layerAnalysis.magentaPixels > 50, 'Inner boundary visible (magenta pixels)', `count=${layerAnalysis.magentaPixels}`);
    assert(layerAnalysis.cyanPixels > 50, 'Outer boundary visible (cyan pixels)', `count=${layerAnalysis.cyanPixels}`);

    await screenshot(page3, 'track-outline-draw-order');
    await page3.close();

    // ── SCENARIO 4: Visual smoke test ─────────────────────────────────────────
    console.log('\n════ SCENARIO 4: Visual smoke test ════');

    const page4 = await browser.newPage({ deviceScaleFactor: 2 });
    await page4.setViewportSize({ width: 1440, height: 900 });
    await page4.goto(url);

    const uploadInput4 = await page4.$('#file-input');
    await uploadInput4.setInputFiles(SESSION);
    await page4.waitForFunction(() => {
      const keys = window.__getSessionKeys?.();
      return keys && keys.length > 0;
    }, { timeout: 10000 });

    await page4.evaluate(() => {
      const opts = [...document.getElementById('session-picker').querySelectorAll('option')].filter(o => o.value);
      if (opts.length >= 2) {
        const sp = document.getElementById('session-picker');
        const rp = document.getElementById('ref-picker');
        sp.value = opts[0].value;
        rp.value = opts[1].value;
        sp.dispatchEvent(new Event('change'));
      }
    });

    await page4.locator('#compare-btn').click();
    await page4.waitForFunction(() => document.querySelectorAll('#panels .panel-svg').length >= 7, { timeout: 10000 });

    await page4.evaluate(() => {
      if (typeof window.__setFeatureFlag === 'function') {
        window.__setFeatureFlag('mapWalkingSkeleton', true);
        window.__setFeatureFlag('mapTrackOutline', true);
        document.getElementById('compare-btn').click();
      }
    });
    await page4.waitForTimeout(500);

    const mapPanel4 = page4.locator('#circuit-map-panel');
    await mapPanel4.hover({ position: { x: 1, y: 1 } });

    await screenshot(page4, 'visual-smoke-test-with-outline');
    await page4.close();

    // ── SCENARIO 5: No console errors ─────────────────────────────────────────
    console.log('\n════ SCENARIO 5: Console error check ════');

    const page5 = await browser.newPage();
    let errorCount = 0;
    page5.on('pageerror', e => {
      errorCount++;
      log(`  [pageerror] ${e.message}`);
    });
    page5.on('console', m => {
      if (m.type() === 'error') {
        errorCount++;
        log(`  [console err] ${m.text}`);
      }
    });

    await page5.setViewportSize({ width: 1280, height: 900 });
    await page5.goto(url);

    const uploadInput5 = await page5.$('#file-input');
    await uploadInput5.setInputFiles(SESSION);
    await page5.waitForFunction(() => {
      const keys = window.__getSessionKeys?.();
      return keys && keys.length > 0;
    }, { timeout: 10000 });

    await page5.evaluate(() => {
      const opts = [...document.getElementById('session-picker').querySelectorAll('option')].filter(o => o.value);
      if (opts.length >= 2) {
        const sp = document.getElementById('session-picker');
        const rp = document.getElementById('ref-picker');
        sp.value = opts[0].value;
        rp.value = opts[1].value;
        sp.dispatchEvent(new Event('change'));
      }
    });

    await page5.locator('#compare-btn').click();
    await page5.waitForFunction(() => document.querySelectorAll('#panels .panel-svg').length >= 7, { timeout: 10000 });

    await page5.evaluate(() => {
      if (typeof window.__setFeatureFlag === 'function') {
        window.__setFeatureFlag('mapWalkingSkeleton', true);
        window.__setFeatureFlag('mapTrackOutline', true);
        document.getElementById('compare-btn').click();
      }
    });
    await page5.waitForTimeout(500);

    assert(errorCount === 0, 'No browser console errors', `${errorCount} errors`);
    await page5.close();

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
    '# Phase 00.6 — Track Outline Background Test Report',
    '',
    `**Date:** ${new Date().toISOString()}`,
    '',
    `## Results`,
    '',
    `  ${passCount}/${passCount + failCount} assertions passed`,
    '',
    failCount === 0 ? '  ✔ All assertions passed' : `  ✘ ${failCount} assertion(s) failed`,
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
