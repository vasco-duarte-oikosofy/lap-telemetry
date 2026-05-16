/**
 * Phase 05a — Linked Highlight Band from Trace Charts Test Suite
 *
 * Run: node scripts/test_05a_linked_highlight.js
 */

'use strict';

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'product', 'web');
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', '05a-test-report');
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
    '# Phase 05a Test Report',
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

async function runTests() {
  console.log('═══ Phase 05a — Linked Highlight Band Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url);

    console.log('════ SCENARIO 1: feature flag exposed ════');
    const flags = await page.evaluate(() => Object.keys(window.__features || {}));
    assert(flags.includes('mapLinkedHighlight'), 'mapLinkedHighlight feature flag is exposed', flags.join(', '));

    console.log('\n════ SCENARIO 2: highlight band geometry (start/end ticks) ════');
    const geo = await page.evaluate(async () => {
      const { renderWalkingSkeleton, fitToView } = await import('/js/trackHeatmapMap.js');
      const canvas = document.createElement('canvas');
      canvas.id = 'phase-05a-geo-canvas';
      canvas.style.width = '500px';
      canvas.style.height = '200px';
      document.body.appendChild(canvas);
      if (!canvas.getBoundingClientRect._shimmed) {
        canvas.getBoundingClientRect = () => ({ width: 500, height: 200, left: 0, top: 0, right: 500, bottom: 200 });
      }

      // 1000 m horizontal track at z=0
      const lapA = {
        x: new Float64Array(1001),
        z: new Float64Array(1001),
        throttle: new Float64Array(1001),
        brake: new Float64Array(1001),
        color: '#4fc3f7',
      };
      for (let i = 0; i <= 1000; i++) {
        lapA.x[i] = i;
        lapA.z[i] = 0;
        // Throttle on right half, brake on left half
        lapA.throttle[i] = i > 500 ? 1 : 0;
        lapA.brake[i] = i < 500 ? 1 : 0;
      }

      const lapB = {
        x: new Float64Array(1001),
        z: new Float64Array(1001),
        throttle: new Float64Array(1001),
        brake: new Float64Array(1001),
        color: '#ff9800',
      };
      for (let i = 0; i <= 1000; i++) {
        lapB.x[i] = i;
        lapB.z[i] = 0;
        lapB.throttle[i] = i > 500 ? 1 : 0;
        lapB.brake[i] = i < 500 ? 1 : 0;
      }

      const visibleRange = { start: 400, end: 800 };

      renderWalkingSkeleton(canvas, lapA, lapB, {
        showDualRibbon: true,
        showLinkedHighlight: true,
        visibleRange,
        ribbonWidthPx: 8,
        ribbonGapPx: 2,
      });

      const tf = fitToView(
        { minX: 0, maxX: 1000, minZ: 0, maxZ: 0 },
        { minX: 0, maxX: 1000, minZ: 0, maxZ: 0 },
        500, 200, 15
      );

      const ctx = canvas.getContext('2d');
      function sample(x, y) {
        const d = ctx.getImageData(Math.round(x), Math.round(y), 1, 1).data;
        return { r: d[0], g: d[1], b: d[2] };
      }

      const centerY = tf.toScreenY(0);
      // Ticks are perpendicular to horizontal track → vertical lines
      // The highlight stroke spans ribbonWidthPx + 10 = 18px around centerline
      // Total span across both ribbons: offsetA=-5, offsetB=+5, halfWidth=4
      // outerA = -9, outerB = +9. With +6 overshoot on tick: span ≈ ±15
      const halfSpan = 8 / 2 + 2 / 2 + 6; // = 11
      const tickTop = centerY - halfSpan;
      const tickBottom = centerY + halfSpan;

      const startX = Math.round(tf.toScreenX(400));
      const endX = Math.round(tf.toScreenX(800));

      // Sample vertical columns at startX and endX looking for white pixels
      const startColumn = [];
      const endColumn = [];
      for (let y = Math.round(tickTop) - 2; y <= Math.round(tickBottom) + 2; y++) {
        startColumn.push({ y, pixel: sample(startX, y) });
        endColumn.push({ y, pixel: sample(endX, y) });
      }

      // Also sample a point well inside the highlight band (s=600) and outside (s=200)
      const insideX = Math.round(tf.toScreenX(600));
      const outsideX = Math.round(tf.toScreenX(200));

      return {
        startX,
        endX,
        centerY,
        startColumn,
        endColumn,
        insidePixel: sample(insideX, Math.round(centerY)),
        outsidePixel: sample(outsideX, Math.round(centerY)),
      };
    });

    const isBright = (p) => p.r + p.g + p.b > 400;

    const startBrightCount = geo.startColumn.filter(c => isBright(c.pixel)).length;
    const endBrightCount = geo.endColumn.filter(c => isBright(c.pixel)).length;

    assert(startBrightCount >= 5, 'start tick has bright pixels at s=400',
      `${startBrightCount} bright pixels at x=${geo.startX}`);
    assert(endBrightCount >= 5, 'end tick has bright pixels at s=800',
      `${endBrightCount} bright pixels at x=${geo.endX}`);

    console.log('\n════ SCENARIO 3: pixel inside highlight stays throttle-green ════');
    // At s=600 (inside highlight), throttle=1, so base color is throttle-green.
    // After lighten composite it should still be green-dominant.
    const pIn = geo.insidePixel;
    const isGreenDominant = (p) => p.g > p.r + 10 && p.g > p.b + 10;
    assert(isGreenDominant(pIn), 'pixel inside highlight at throttle zone stays green-dominant',
      JSON.stringify(pIn));

    console.log('\n════ SCENARIO 4: no visibleRange renders identically to Phase 4 ════');
    const baseline = await page.evaluate(async () => {
      const { renderWalkingSkeleton } = await import('/js/trackHeatmapMap.js');
      const canvas = document.createElement('canvas');
      canvas.id = 'phase-05a-baseline-canvas';
      canvas.style.width = '500px';
      canvas.style.height = '200px';
      document.body.appendChild(canvas);
      if (!canvas.getBoundingClientRect._shimmed) {
        canvas.getBoundingClientRect = () => ({ width: 500, height: 200, left: 0, top: 0, right: 500, bottom: 200 });
      }

      const lapA = {
        x: new Float64Array([0, 200, 400, 600, 800, 1000]),
        z: new Float64Array([0, 0, 0, 0, 0, 0]),
        throttle: new Float64Array([0, 0, 0, 1, 1, 1]),
        brake: new Float64Array([1, 1, 0, 0, 0, 0]),
        color: '#4fc3f7',
      };
      const lapB = {
        x: new Float64Array([0, 200, 400, 600, 800, 1000]),
        z: new Float64Array([0, 0, 0, 0, 0, 0]),
        throttle: new Float64Array([1, 1, 0, 0, 0, 0]),
        brake: new Float64Array([0, 0, 0, 1, 1, 1]),
        color: '#ff9800',
      };

      renderWalkingSkeleton(canvas, lapA, lapB, {
        showDualRibbon: true,
        ribbonWidthPx: 8,
        ribbonGapPx: 2,
      });

      const ctx = canvas.getContext('2d');
      return ctx.getImageData(0, 0, 500, 200).data;
    });

    const withFlagNoRange = await page.evaluate(async () => {
      const { renderWalkingSkeleton } = await import('/js/trackHeatmapMap.js');
      const canvas = document.createElement('canvas');
      canvas.id = 'phase-05a-norange-canvas';
      canvas.style.width = '500px';
      canvas.style.height = '200px';
      document.body.appendChild(canvas);
      if (!canvas.getBoundingClientRect._shimmed) {
        canvas.getBoundingClientRect = () => ({ width: 500, height: 200, left: 0, top: 0, right: 500, bottom: 200 });
      }

      const lapA = {
        x: new Float64Array([0, 200, 400, 600, 800, 1000]),
        z: new Float64Array([0, 0, 0, 0, 0, 0]),
        throttle: new Float64Array([0, 0, 0, 1, 1, 1]),
        brake: new Float64Array([1, 1, 0, 0, 0, 0]),
        color: '#4fc3f7',
      };
      const lapB = {
        x: new Float64Array([0, 200, 400, 600, 800, 1000]),
        z: new Float64Array([0, 0, 0, 0, 0, 0]),
        throttle: new Float64Array([1, 1, 0, 0, 0, 0]),
        brake: new Float64Array([0, 0, 0, 1, 1, 1]),
        color: '#ff9800',
      };

      renderWalkingSkeleton(canvas, lapA, lapB, {
        showDualRibbon: true,
        showLinkedHighlight: true,
        ribbonWidthPx: 8,
        ribbonGapPx: 2,
      });

      const ctx = canvas.getContext('2d');
      return ctx.getImageData(0, 0, 500, 200).data;
    });

    let diffCount = 0;
    for (let i = 0; i < baseline.length; i++) {
      if (baseline[i] !== withFlagNoRange[i]) {
        diffCount++;
      }
    }
    assert(diffCount === 0, 'no visibleRange renders identically to baseline (no highlight)', `${diffCount} pixels differed`);

    console.log('\n════ SCENARIO 5: full-lap visibleRange is a no-op ════');
    const fullRange = await page.evaluate(async () => {
      const { renderWalkingSkeleton } = await import('/js/trackHeatmapMap.js');
      const canvas = document.createElement('canvas');
      canvas.id = 'phase-05a-fullrange-canvas';
      canvas.style.width = '500px';
      canvas.style.height = '200px';
      document.body.appendChild(canvas);
      if (!canvas.getBoundingClientRect._shimmed) {
        canvas.getBoundingClientRect = () => ({ width: 500, height: 200, left: 0, top: 0, right: 500, bottom: 200 });
      }

      const lapA = {
        x: new Float64Array([0, 200, 400, 600, 800, 1000]),
        z: new Float64Array([0, 0, 0, 0, 0, 0]),
        throttle: new Float64Array([0, 0, 0, 1, 1, 1]),
        brake: new Float64Array([1, 1, 0, 0, 0, 0]),
        color: '#4fc3f7',
      };
      const lapB = {
        x: new Float64Array([0, 200, 400, 600, 800, 1000]),
        z: new Float64Array([0, 0, 0, 0, 0, 0]),
        throttle: new Float64Array([1, 1, 0, 0, 0, 0]),
        brake: new Float64Array([0, 0, 0, 1, 1, 1]),
        color: '#ff9800',
      };

      renderWalkingSkeleton(canvas, lapA, lapB, {
        showDualRibbon: true,
        showLinkedHighlight: true,
        visibleRange: { start: 0, end: 1000 },
        ribbonWidthPx: 8,
        ribbonGapPx: 2,
      });

      const ctx = canvas.getContext('2d');
      return ctx.getImageData(0, 0, 500, 200).data;
    });

    let fullDiffCount = 0;
    for (let i = 0; i < baseline.length; i++) {
      if (baseline[i] !== fullRange[i]) {
        fullDiffCount++;
      }
    }
    assert(fullDiffCount === 0, 'full-lap visibleRange is a no-op', `${fullDiffCount} pixels differed`);

    console.log('\n════ SCENARIO 6: event-loop paint within 100 ms ════');
    const paintTime = await page.evaluate(async () => {
      const { renderWalkingSkeleton } = await import('/js/trackHeatmapMap.js');
      const canvas = document.createElement('canvas');
      canvas.style.width = '500px';
      canvas.style.height = '200px';
      document.body.appendChild(canvas);
      if (!canvas.getBoundingClientRect._shimmed) {
        canvas.getBoundingClientRect = () => ({ width: 500, height: 200, left: 0, top: 0, right: 500, bottom: 200 });
      }

      const lapA = {
        x: new Float64Array(1001),
        z: new Float64Array(1001),
        throttle: new Float64Array(1001),
        brake: new Float64Array(1001),
        color: '#4fc3f7',
      };
      const lapB = {
        x: new Float64Array(1001),
        z: new Float64Array(1001),
        throttle: new Float64Array(1001),
        brake: new Float64Array(1001),
        color: '#ff9800',
      };
      for (let i = 0; i <= 1000; i++) {
        lapA.x[i] = i; lapA.z[i] = 0; lapA.throttle[i] = i > 500 ? 1 : 0; lapA.brake[i] = i < 500 ? 1 : 0;
        lapB.x[i] = i; lapB.z[i] = 0; lapB.throttle[i] = i > 500 ? 1 : 0; lapB.brake[i] = i < 500 ? 1 : 0;
      }

      const start = performance.now();
      renderWalkingSkeleton(canvas, lapA, lapB, {
        showDualRibbon: true,
        showLinkedHighlight: true,
        visibleRange: { start: 100, end: 900 },
        ribbonWidthPx: 8,
        ribbonGapPx: 2,
      });
      const end = performance.now();
      return end - start;
    });

    assert(paintTime < 100, 'highlight render completes within 100ms', `${paintTime.toFixed(2)} ms`);

    console.log('\n════ SCENARIO 7: resize does not change highlight s boundaries ════');
    const resizeCheck = await page.evaluate(async () => {
      const { renderWalkingSkeleton, fitToView } = await import('/js/trackHeatmapMap.js');

      const lapA = {
        x: new Float64Array(1001),
        z: new Float64Array(1001),
        throttle: new Float64Array(1001),
        brake: new Float64Array(1001),
        color: '#4fc3f7',
      };
      const lapB = {
        x: new Float64Array(1001),
        z: new Float64Array(1001),
        throttle: new Float64Array(1001),
        brake: new Float64Array(1001),
        color: '#ff9800',
      };
      for (let i = 0; i <= 1000; i++) {
        lapA.x[i] = i; lapA.z[i] = 0;
        lapB.x[i] = i; lapB.z[i] = 0;
      }

      const visibleRange = { start: 400, end: 800 };

      // Render at 500x200
      const c1 = document.createElement('canvas');
      c1.style.width = '500px';
      c1.style.height = '200px';
      document.body.appendChild(c1);
      c1.getBoundingClientRect = () => ({ width: 500, height: 200 });
      renderWalkingSkeleton(c1, lapA, lapB, {
        showDualRibbon: true,
        showLinkedHighlight: true,
        visibleRange,
        ribbonWidthPx: 8,
        ribbonGapPx: 2,
      });
      const tf1 = fitToView(
        { minX: 0, maxX: 1000, minZ: 0, maxZ: 0 },
        { minX: 0, maxX: 1000, minZ: 0, maxZ: 0 },
        500, 200, 15
      );
      const ctx1 = c1.getContext('2d');
      function findBrightColumn(ctx, w, h, expectedX) {
        for (let x = Math.max(0, expectedX - 3); x <= Math.min(w - 1, expectedX + 3); x++) {
          let brightCount = 0;
          for (let y = 0; y < h; y++) {
            const d = ctx.getImageData(x, y, 1, 1).data;
            if (d[0] + d[1] + d[2] > 400) brightCount++;
          }
          if (brightCount >= 5) return x;
        }
        return -1;
      }
      const startX1 = findBrightColumn(ctx1, 500, 200, Math.round(tf1.toScreenX(400)));
      const endX1 = findBrightColumn(ctx1, 500, 200, Math.round(tf1.toScreenX(800)));

      // Render at 300x150
      const c2 = document.createElement('canvas');
      c2.style.width = '300px';
      c2.style.height = '150px';
      document.body.appendChild(c2);
      c2.getBoundingClientRect = () => ({ width: 300, height: 150 });
      renderWalkingSkeleton(c2, lapA, lapB, {
        showDualRibbon: true,
        showLinkedHighlight: true,
        visibleRange,
        ribbonWidthPx: 8,
        ribbonGapPx: 2,
      });
      const tf2 = fitToView(
        { minX: 0, maxX: 1000, minZ: 0, maxZ: 0 },
        { minX: 0, maxX: 1000, minZ: 0, maxZ: 0 },
        300, 150, 15
      );
      const ctx2 = c2.getContext('2d');
      const startX2 = findBrightColumn(ctx2, 300, 150, Math.round(tf2.toScreenX(400)));
      const endX2 = findBrightColumn(ctx2, 300, 150, Math.round(tf2.toScreenX(800)));

      return {
        startX1,
        endX1,
        startX2,
        endX2,
        expectedStart1: Math.round(tf1.toScreenX(400)),
        expectedEnd1: Math.round(tf1.toScreenX(800)),
        expectedStart2: Math.round(tf2.toScreenX(400)),
        expectedEnd2: Math.round(tf2.toScreenX(800)),
      };
    });

    const startOk1 = Math.abs(resizeCheck.startX1 - resizeCheck.expectedStart1) <= 1;
    const endOk1 = Math.abs(resizeCheck.endX1 - resizeCheck.expectedEnd1) <= 1;
    const startOk2 = Math.abs(resizeCheck.startX2 - resizeCheck.expectedStart2) <= 1;
    const endOk2 = Math.abs(resizeCheck.endX2 - resizeCheck.expectedEnd2) <= 1;

    assert(startOk1,
      'start tick at 500x200 is within 1px of expected s=400 position',
      `found ${resizeCheck.startX1}, expected ${resizeCheck.expectedStart1}`);
    assert(endOk1,
      'end tick at 500x200 is within 1px of expected s=800 position',
      `found ${resizeCheck.endX1}, expected ${resizeCheck.expectedEnd1}`);
    assert(startOk2,
      'start tick at 300x150 is within 1px of expected s=400 position',
      `found ${resizeCheck.startX2}, expected ${resizeCheck.expectedStart2}`);
    assert(endOk2,
      'end tick at 300x150 is within 1px of expected s=800 position',
      `found ${resizeCheck.endX2}, expected ${resizeCheck.expectedEnd2}`);

    // Screenshot artifact
    const png = await page.screenshot({ path: path.join(SHOTS_DIR, 'phase-05a-page.png') });
    assert(png.length > 0, 'phase-05a page screenshot written', `${png.length} bytes`);

  } finally {
    await browser.close();
    server.close();
  }

  writeReport();
  if (failCount > 0) throw new Error(`${failCount} Phase 05a assertions failed`);
}

runTests().catch(err => {
  console.error(err);
  writeReport();
  process.exit(1);
});
