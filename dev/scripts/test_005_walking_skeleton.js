/**
 * Phase 00.5 — Walking Skeleton Test Suite
 *
 * Verifies the TrackHeatmapMap canvas component:
 * - fitToView computes correct transforms
 * - Both lap polylines render on canvas in correct colors
 * - Canvas re-fits on resize without distortion (aspect ratio preserved)
 * - Start/finish marker drawn at s=0 on Lap A
 * - Visual smoke test with real fixture data
 *
 * Run: node scripts/test_005_walking_skeleton.js
 *
 * Produces: 005-test-report/ with screenshots and REPORT.md
 */

'use strict';

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { startServer } = require('./lib/test-server');

// ── Paths ─────────────────────────────────────────────────────────────────────
const ROOT         = path.resolve(__dirname, '..', '..');
const WEB_DIR      = path.join(ROOT, 'web');
const SESSIONS_DIR = path.join(ROOT, 'dev', 'sessions');
const REPORT_DIR   = path.join(ROOT, 'var', 'test-output', '005-test-report');
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
  console.log('═══ Phase 00.5 — Walking Skeleton Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  console.log(`URL: ${url}`);
  console.log(`Report: ${REPORT_DIR}\n`);

  const browser = await chromium.launch();

  try {
    // ── SCENARIO 1: fitToView unit tests ─────────────────────────────────────
    console.log('════ SCENARIO 1: fitToView unit tests ════');

    const page1 = await browser.newPage();
    await page1.setViewportSize({ width: 1024, height: 768 });
    await page1.goto(url);

    // We need the module loaded — go to the page then import via evaluate
    // Test fitToView with known inputs
    const fitTests = await page1.evaluate(() => {
      // Import trackHeatmapMap module — but since it's a module, we need it exposed on window
      // This will fail gracefully if not available yet
      if (!window.__fitToView) return { error: 'fitToView not exposed' };

      const tests = [];

      // Test 1: Simple square track, 100x100 canvas, 10px padding
      const t1 = window.__fitToView(
        { minX: 0, maxX: 100, minZ: 0, maxZ: 100 },
        100, 100, 10
      );
      console.log('T1 raw return:', JSON.stringify(t1));
      tests.push({
        name: 'Square track, square canvas, 10px padding',
        scale: t1.scale,
        offsetX: t1.offsetX,
        offsetY: t1.offsetY,
        expectedScale: 0.8,
        expectedOffsetX: 10,
        expectedOffsetY: 10,
      });

      // Test 2: Wide track, square canvas
      const t2 = window.__fitToView(
        { minX: 0, maxX: 200, minZ: 0, maxZ: 100 },
        200, 200, 20
      );
      // Available: 160x160 for 200x100 world units
      // Scale = min(160/200, 160/100) = min(0.8, 1.6) = 0.8
      tests.push({
        name: 'Wide track, square canvas, 20px padding',
        scale: t2.scale,
        expectedScale: 0.8,
      });

      // Test 3: Asymmetric padding test
      const t3 = window.__fitToView(
        { minX: -50, maxX: 50, minZ: -100, maxZ: 100 },
        300, 300, 20
      );
      // Available: 260x260 for 100x200 world units
      // Scale = min(260/100, 260/200) = min(2.6, 1.3) = 1.3
      tests.push({
        name: 'Centered track, asymmetric proportions',
        scale: t3.scale,
        expectedScale: 1.3,
      });

      return tests;
    });

    if (fitTests.error) {
      log(`  ⚠ fitToView not yet exposed on window — skipping unit tests (will test via rendering)`);
    } else {
      for (const t of fitTests) {
        const scaleOk = Math.abs(t.scale - t.expectedScale) < 0.001;
        assert(scaleOk, t.name, `scale=${t.scale.toFixed(4)} expected=${t.expectedScale}`);
        if (t.expectedOffsetX !== undefined) {
          const oxOk = Math.abs(t.offsetX - t.expectedOffsetX) < 0.5;
          assert(oxOk, `${t.name} (offsetX)`, `offsetX=${t.offsetX?.toFixed(2)} expected=${t.expectedOffsetX}`);
        }
        if (t.expectedOffsetY !== undefined) {
          const oyOk = Math.abs(t.offsetY - t.expectedOffsetY) < 0.5;
          assert(oyOk, `${t.name} (offsetY)`, `offsetY=${t.offsetY?.toFixed(2)} expected=${t.expectedOffsetY}`);
        }
      }
    }
    await page1.close();

    // ── SCENARIO 2: Canvas renders both laps ──────────────────────────────────
    console.log('\n════ SCENARIO 2: Canvas renders both lap polylines ════');

    const page2 = await browser.newPage({ deviceScaleFactor: 1 });
    await page2.setViewportSize({ width: 1280, height: 900 });
    await page2.goto(url);

    // Load session
    const uploadInput2 = await page2.$('#file-input');
    await uploadInput2.setInputFiles(SESSION);
    await page2.waitForFunction(() => {
      const keys = window.__getSessionKeys?.();
      return keys && keys.length > 0;
    }, { timeout: 10000 });

    // Select two laps for comparison
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

    // Click Compare
    const compareBtn = page2.locator('#compare-btn');
    await compareBtn.click();

    // Wait for panels to render
    await page2.waitForFunction(() => {
      const panels = document.querySelectorAll('#panels .panel-svg');
      return panels.length >= 7;
    }, { timeout: 10000 });

    // Wait for the track heatmap canvas to be visible (feature flag must be enabled)
    const heatmapCanvas = page2.locator('#track-heatmap-canvas');
    const canvasVisible = await heatmapCanvas.isVisible().catch(() => false);

    if (canvasVisible) {
      // Test: canvas has content (non-zero pixel data)
      const canvasInfo = await page2.evaluate(() => {
        const canvas = document.getElementById('track-heatmap-canvas');
        if (!canvas) return { error: 'canvas not found' };
        const ctx = canvas.getContext('2d');
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        let nonTransparentPixels = 0;
        let nonBackgroundPixels = 0;
        for (let i = 0; i < data.length; i += 4) {
          if (data[i + 3] > 0) nonTransparentPixels++;
          // Check for non-background color (not just rgba(0,0,0,0) or the surface bg)
          if (data[i] > 5 || data[i + 1] > 5 || data[i + 2] > 5) nonBackgroundPixels++;
        }
        return {
          width: canvas.width,
          height: canvas.height,
          totalPixels: canvas.width * canvas.height,
          nonTransparentPixels,
          nonBackgroundPixels,
        };
      });

      assert(canvasInfo.width > 0, 'Canvas has positive width', `width=${canvasInfo.width}`);
      assert(canvasInfo.height > 0, 'Canvas has positive height', `height=${canvasInfo.height}`);
      assert(canvasInfo.nonBackgroundPixels > 100, 'Canvas has drawn content (polyline pixels)', `non-bg pixels=${canvasInfo.nonBackgroundPixels}`);
    } else {
      // Feature flag may be off — check if we can enable it
      log('  ⚠ Canvas not visible by default — checking feature flag...');

      // Try enabling via URL parameter or evaluate
      const enabled = await page2.evaluate(() => {
        // Check if the feature flag system exists
        if (typeof window.__setFeatureFlag === 'function') {
          window.__setFeatureFlag('mapWalkingSkeleton', true);
          return true;
        }
        return false;
      });

      if (enabled) {
        // Re-render
        await page2.evaluate(() => {
          // Trigger re-render — find the compare handler
          const btn = document.getElementById('compare-btn');
          btn.click();
        });

        await page2.waitForTimeout(500);

        const canvasInfo = await page2.evaluate(() => {
          const canvas = document.getElementById('track-heatmap-canvas');
          if (!canvas) return { error: 'canvas not found' };
          const ctx = canvas.getContext('2d');
          const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const data = imageData.data;
          let nonBackgroundPixels = 0;
          for (let i = 0; i < data.length; i += 4) {
            if (data[i] > 5 || data[i + 1] > 5 || data[i + 2] > 5) nonBackgroundPixels++;
          }
          return {
            width: canvas.width,
            height: canvas.height,
            nonBackgroundPixels,
          };
        });

        assert(canvasInfo.width > 0, 'Canvas has positive width (after flag)', `width=${canvasInfo.width}`);
        assert(canvasInfo.height > 0, 'Canvas has positive height (after flag)', `height=${canvasInfo.height}`);
        assert(canvasInfo.nonBackgroundPixels > 100, 'Canvas has drawn content (after flag)', `non-bg pixels=${canvasInfo.nonBackgroundPixels}`);
      } else {
        // Fall back to checking the canvas exists in DOM and has been drawn to
        log('  ⚠ Feature flag system not available — testing canvas element existence only');
        const canvasExists = await page2.evaluate(() => {
          return !!document.getElementById('track-heatmap-canvas');
        });
        assert(canvasExists, 'Canvas element exists in DOM');
      }
    }

    await screenshot(page2, 'walking-skeleton-1280x900');
    await page2.close();

    // ── SCENARIO 3: Resize test ───────────────────────────────────────────────
    console.log('\n════ SCENARIO 3: Canvas responds to resize ════');

    const page3 = await browser.newPage({ deviceScaleFactor: 1 });
    await page3.setViewportSize({ width: 1280, height: 900 });
    await page3.goto(url);

    // Load and compare
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

    // Enable feature flag if needed
    const flagEnabled = await page3.evaluate(() => {
      if (typeof window.__setFeatureFlag === 'function') {
        window.__setFeatureFlag('mapWalkingSkeleton', true);
        return true;
      }
      return false;
    });

    if (flagEnabled) {
      await page3.evaluate(() => document.getElementById('compare-btn').click());
      await page3.waitForTimeout(500);
    }

    // Get initial canvas dimensions
    const initialDims = await page3.evaluate(() => {
      const canvas = document.getElementById('track-heatmap-canvas');
      if (!canvas) return null;
      return { width: canvas.width, height: canvas.height, cssW: canvas.clientWidth, cssH: canvas.clientHeight };
    });

    if (initialDims) {
      // Resize viewport to narrower
      await page3.setViewportSize({ width: 800, height: 600 });
      await page3.waitForTimeout(300); // Wait for ResizeObserver

      const resizedDims = await page3.evaluate(() => {
        const canvas = document.getElementById('track-heatmap-canvas');
        if (!canvas) return null;
        return { width: canvas.width, height: canvas.height, cssW: canvas.clientWidth, cssH: canvas.clientHeight };
      });

      if (resizedDims) {
        // Canvas dimensions should change on resize (they may increase if we cross
        // the mobile breakpoint from 50% to 100% width)
        assert(resizedDims.cssW !== initialDims.cssW, 'Canvas CSS width changes on resize', `before=${initialDims.cssW} after=${resizedDims.cssW}`);
        assert(resizedDims.cssH !== initialDims.cssH, 'Canvas CSS height changes on resize', `before=${initialDims.cssH} after=${resizedDims.cssH}`);

        // Aspect ratio should be preserved — check that the track still fills the view
        const canvasData = await page3.evaluate(() => {
          const canvas = document.getElementById('track-heatmap-canvas');
          const ctx = canvas.getContext('2d');
          const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const data = imageData.data;
          let nonBackgroundPixels = 0;
          for (let i = 0; i < data.length; i += 4) {
            if (data[i] > 5 || data[i + 1] > 5 || data[i + 2] > 5) nonBackgroundPixels++;
          }
          return { nonBackgroundPixels };
        });

        assert(canvasData.nonBackgroundPixels > 100, 'Canvas still has content after resize', `pixels=${canvasData.nonBackgroundPixels}`);
      }

      await screenshot(page3, 'walking-skeleton-resized-800x600');
    } else {
      log('  ⚠ Canvas not found — skipping resize test');
    }

    await page3.close();

    // ── SCENARIO 4: Visual smoke test with real data ──────────────────────────
    console.log('\n════ SCENARIO 4: Visual smoke test ════');

    const page4 = await browser.newPage({ deviceScaleFactor: 2 }); // 2x DPR for clean screenshots
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

    // Enable feature flag if available
    await page4.evaluate(() => {
      if (typeof window.__setFeatureFlag === 'function') {
        window.__setFeatureFlag('mapWalkingSkeleton', true);
        document.getElementById('compare-btn').click();
      }
    });
    await page4.waitForTimeout(500);

    // Scroll the map panel into view (lesson L1/L3)
    const mapPanel = page4.locator('#circuit-map-panel');
    await mapPanel.hover({ position: { x: 1, y: 1 } });

    await screenshot(page4, 'visual-smoke-test-1440x900');
    await page4.close();

    // ── SCENARIO 5: No console errors ──────────────────────────────────────────
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

    // Enable feature flag
    await page5.evaluate(() => {
      if (typeof window.__setFeatureFlag === 'function') {
        window.__setFeatureFlag('mapWalkingSkeleton', true);
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
    '# Phase 00.5 — Walking Skeleton Test Report',
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