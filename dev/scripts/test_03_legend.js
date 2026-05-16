/**
 * Phase 03 — Lap Legend and Identification Test Suite
 *
 * Run: node scripts/test_03_legend.js
 */

'use strict';

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'web');
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', '03-test-report');
const SHOTS_DIR = path.join(REPORT_DIR, 'screenshots');
fs.mkdirSync(SHOTS_DIR, { recursive: true });

const results = [];
let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  results.push({ status, name, detail });
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function writeReport() {
  const lines = [
    '# Phase 03 Test Report',
    '',
    `Passed: ${passCount}`,
    `Failed: ${failCount}`,
    '',
    '| Status | Assertion | Detail |',
    '|--------|-----------|--------|',
    ...results.map(r => `| ${r.status} | ${r.name} | ${String(r.detail).replace(/\|/g, '\\|')} |`),
  ];
  fs.writeFileSync(path.join(REPORT_DIR, 'REPORT.md'), lines.join('\n'));
}

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function colorClose(p, hex, tol = 8) {
  const e = hexToRgb(hex);
  return Math.abs(p.r - e.r) <= tol && Math.abs(p.g - e.g) <= tol && Math.abs(p.b - e.b) <= tol;
}

async function runTests() {
  console.log('═══ Phase 03 — Lap Legend and Identification Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url);

    console.log('════ SCENARIO 1: feature flag exposed ════');
    const flags = await page.evaluate(() => Object.keys(window.__features || {}));
    assert(flags.includes('mapLegend'), 'mapLegend feature flag is exposed', flags.join(', '));

    console.log('\n════ SCENARIO 2: lap legend DOM appears when flag enabled ════');
    await page.evaluate(() => {
      document.getElementById('circuit-map-panel').style.display = 'block';
      window.__setFeatureFlag('mapLegend', true);
      window.__setFeatureFlag('mapDualRibbon', true);
    });

    // Trigger a render with synthetic data
    await page.evaluate(async () => {
      const { renderWalkingSkeleton } = await import('/js/trackHeatmapMap.js');
      const canvas = document.getElementById('track-heatmap-canvas');
      canvas.style.width = '400px';
      canvas.style.height = '200px';
      if (!canvas.getBoundingClientRect._shimmed) {
        canvas.getBoundingClientRect = () => ({ width: 400, height: 200, left: 0, top: 0, right: 400, bottom: 200 });
      }
      const lapA = {
        x: new Float64Array([0, 50, 100, 150, 200]),
        z: new Float64Array([0, 0, 0, 0, 0]),
        throttle: new Float64Array([0, 0, 0, 1, 1]),
        brake: new Float64Array([1, 1, 0, 0, 0]),
        color: '#4fc3f7',
      };
      const lapB = {
        x: new Float64Array([0, 50, 100, 150, 200]),
        z: new Float64Array([0, 0, 0, 0, 0]),
        throttle: new Float64Array([1, 1, 0, 0, 0]),
        brake: new Float64Array([0, 0, 0, 1, 1]),
        color: '#ff9800',
      };
      renderWalkingSkeleton(canvas, lapA, lapB, {
        showDualRibbon: true,
        showLegend: true,
        ribbonWidthPx: 8,
        ribbonGapPx: 2,
      });
    });

    const lapLegend = await page.$('#map-lap-legend');
    assert(!!lapLegend, 'lap legend overlay exists in DOM');

    const lapLegendVisible = await page.evaluate(() => {
      const el = document.getElementById('map-lap-legend');
      return el && getComputedStyle(el).display !== 'none';
    });
    assert(lapLegendVisible, 'lap legend overlay is visible');

    const swatchCount = await page.evaluate(() =>
      document.querySelectorAll('#map-lap-legend .legend-swatch').length
    );
    assert(swatchCount === 2, 'lap legend has two swatches', `${swatchCount}`);

    const rampLegend = await page.$('#map-ramp-legend');
    assert(!!rampLegend, 'ramp legend overlay exists in DOM');

    const rampVisible = await page.evaluate(() => {
      const el = document.getElementById('map-ramp-legend');
      return el && getComputedStyle(el).display !== 'none';
    });
    assert(rampVisible, 'ramp legend overlay is visible');

    console.log('\n════ SCENARIO 3: ribbon outer-edge outlines (synthetic pixel test) ════');
    const outlinePixels = await page.evaluate(async () => {
      const { renderWalkingSkeleton, fitToView } = await import('/js/trackHeatmapMap.js');
      const canvas = document.createElement('canvas');
      canvas.id = 'phase-03-outline-canvas';
      canvas.style.width = '240px';
      canvas.style.height = '100px';
      document.body.appendChild(canvas);
      if (!canvas.getBoundingClientRect._shimmed) {
        canvas.getBoundingClientRect = () => ({ width: 240, height: 100, left: 0, top: 0, right: 240, bottom: 100 });
      }

      const lapA = {
        x: new Float64Array([0, 50, 100, 150, 200]),
        z: new Float64Array([0, 0, 0, 0, 0]),
        throttle: new Float64Array([0, 0, 0, 1, 1]),
        brake: new Float64Array([1, 1, 0, 0, 0]),
        color: '#4fc3f7',
      };
      const lapB = {
        x: new Float64Array([0, 50, 100, 150, 200]),
        z: new Float64Array([0, 0, 0, 0, 0]),
        throttle: new Float64Array([1, 1, 0, 0, 0]),
        brake: new Float64Array([0, 0, 0, 1, 1]),
        color: '#ff9800',
      };

      renderWalkingSkeleton(canvas, lapA, lapB, {
        showDualRibbon: true,
        ribbonWidthPx: 8,
        ribbonGapPx: 2,
      });

      const tf = fitToView(
        { minX: 0, maxX: 200, minZ: 0, maxZ: 0 },
        { minX: 0, maxX: 200, minZ: 0, maxZ: 0 },
        240, 100, 15
      );

      const centerY = tf.toScreenY(0);
      // offsetA = -5, halfWidth = 4
      // Lap A outer edge = offsetA - halfWidth = -9  → centerY - 9
      // Lap A inner edge = offsetA + halfWidth = -1  → centerY - 1
      // Lap B inner edge = offsetB - halfWidth = +1  → centerY + 1
      // Lap B outer edge = offsetB + halfWidth = +9  → centerY + 9
      const sampleX = 120;
      const outerA = centerY - 9;
      const innerA = centerY - 1;
      const innerB = centerY + 1;
      const outerB = centerY + 9;

      const ctx = canvas.getContext('2d');
      function sample(x, y) {
        const d = ctx.getImageData(Math.round(x), Math.round(y), 1, 1).data;
        return { r: d[0], g: d[1], b: d[2] };
      }

      return {
        outerA: sample(sampleX, outerA),
        innerA: sample(sampleX, innerA),
        innerB: sample(sampleX, innerB),
        outerB: sample(sampleX, outerB),
        center: sample(sampleX, centerY),
      };
    });

    // Lap A accent color = #4fc3f7 (light blue)
    const isAccentA = (p) => p.r > 60 && p.g > 180 && p.b > 220;
    // Lap B accent color = #ff9800 (orange)
    const isAccentB = (p) => p.r > 220 && p.g > 130 && p.b < 50;
    // Dark = background / gap
    const isDark = (p) => p.r < 60 && p.g < 60 && p.b < 60;

    assert(isAccentA(outlinePixels.outerA), 'Lap A outer edge has accent color outline',
      JSON.stringify(outlinePixels.outerA));
    assert(!isAccentA(outlinePixels.innerA), 'Lap A inner edge does NOT have accent color',
      JSON.stringify(outlinePixels.innerA));
    assert(!isAccentB(outlinePixels.innerB), 'Lap B inner edge does NOT have accent color',
      JSON.stringify(outlinePixels.innerB));
    assert(isAccentB(outlinePixels.outerB), 'Lap B outer edge has accent color outline',
      JSON.stringify(outlinePixels.outerB));
    assert(isDark(outlinePixels.center), 'gap between ribbons remains dark', JSON.stringify(outlinePixels.center));

    console.log('\n════ SCENARIO 4: color-ramp legend pixel exactness ════');
    const rampPixels = await page.evaluate(async () => {
      const { colorForNet } = await import('/js/colorRamp.js');
      const canvas = document.createElement('canvas');
      canvas.width = 161;
      canvas.height = 16;
      const ctx = canvas.getContext('2d');
      for (let x = 0; x < 161; x++) {
        const net = -1 + (2 * x) / 160;
        ctx.fillStyle = colorForNet(net);
        ctx.fillRect(x, 0, 1, 16);
      }
      function sample(x, y) {
        const d = ctx.getImageData(Math.round(x), Math.round(y), 1, 1).data;
        return { r: d[0], g: d[1], b: d[2] };
      }
      return {
        left: sample(0, 8),
        mid: sample(80, 8),
        right: sample(160, 8),
      };
    });

    assert(colorClose(rampPixels.left, '#0a3d91', 4), 'ramp left end is colorForNet(-1)',
      JSON.stringify(rampPixels.left));
    assert(colorClose(rampPixels.mid, '#2a3340', 4), 'ramp middle is colorForNet(0)',
      JSON.stringify(rampPixels.mid));
    assert(colorClose(rampPixels.right, '#0f7a2e', 4), 'ramp right end is colorForNet(1)',
      JSON.stringify(rampPixels.right));

    console.log('\n════ SCENARIO 5: pan/zoom works with legends visible ════');
    await page.evaluate(() => {
      window.__setFeatureFlag('mapZoomPan', true);
      window.__setFeatureFlag('mapLegend', true);
      window.__setFeatureFlag('mapDualRibbon', true);
    });

    const heatmapCanvas = await page.$('#track-heatmap-canvas');
    await heatmapCanvas.hover({ position: { x: 1, y: 1 } });

    const box = await heatmapCanvas.boundingBox();
    const wheelX = Math.round(box.x + box.width * 0.5);
    const wheelY = Math.round(box.y + box.height * 0.5);

    const beforeZoom = await page.evaluate(() => window.__mapZoomPanState?.scale || 1);
    await heatmapCanvas.evaluate((el, cx, cy) => {
      el.dispatchEvent(new WheelEvent('wheel', { deltaY: -100, clientX: cx, clientY: cy, bubbles: true }));
    }, wheelX, wheelY);
    const afterZoom = await page.evaluate(() => window.__mapZoomPanState?.scale || 1);
    assert(afterZoom > beforeZoom, 'wheel zoom works with legends visible',
      `${beforeZoom} → ${afterZoom}`);

    // Pointer events pass through legends
    const legendsPointerEvents = await page.evaluate(() => {
      const lap = document.getElementById('map-lap-legend');
      const ramp = document.getElementById('map-ramp-legend');
      const getPE = (el) => el ? getComputedStyle(el).pointerEvents : 'missing';
      return { lap: getPE(lap), ramp: getPE(ramp) };
    });
    assert(legendsPointerEvents.lap === 'none', 'lap legend has pointer-events: none',
      legendsPointerEvents.lap);
    assert(legendsPointerEvents.ramp === 'none', 'ramp legend has pointer-events: none',
      legendsPointerEvents.ramp);

    // Screenshot artifact
    const png = await page.screenshot({ path: path.join(SHOTS_DIR, 'phase-03-page.png') });
    assert(png.length > 0, 'phase-03 page screenshot written', `${png.length} bytes`);

  } finally {
    await browser.close();
    server.close();
  }

  writeReport();
  if (failCount > 0) throw new Error(`${failCount} Phase 03 assertions failed`);
}

runTests().catch(err => {
  console.error(err);
  writeReport();
  process.exit(1);
});
