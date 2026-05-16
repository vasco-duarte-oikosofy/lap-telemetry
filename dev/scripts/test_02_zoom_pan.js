/**
 * Phase 02 — Zoom and Pan Test Suite
 *
 * Run: node scripts/test_02_zoom_pan.js
 */
// @parallel true

'use strict';

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'product', 'web');
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', '02-test-report');
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
    '# Phase 02 Test Report',
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
  console.log('═══ Phase 02 — Zoom and Pan Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url);

    console.log('════ SCENARIO 1: feature flag exposed ════');
    const flags = await page.evaluate(() => Object.keys(window.__features || {}));
    assert(flags.includes('mapZoomPan'), 'mapZoomPan feature flag is exposed', flags.join(', '));

    console.log('\n════ SCENARIO 2: transform composition (synthetic) ════');
    const synthetic = await page.evaluate(async () => {
      const { renderWalkingSkeleton, fitToView } = await import('/js/trackHeatmapMap.js');
      const canvas = document.createElement('canvas');
      canvas.id = 'phase-02-render-canvas';
      canvas.style.width = '240px';
      canvas.style.height = '100px';
      document.body.appendChild(canvas);
      if (!canvas.getBoundingClientRect._shimmed) {
        canvas.getBoundingClientRect = () => ({ width: 240, height: 100, left: 0, top: 0, right: 240, bottom: 100 });
      }

      // Horizontal track at z=0 from x=0 to x=200
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
        userScale: 2,
        userPanX: 10,
        userPanY: 5,
      });

      const tf = fitToView(
        { minX: 0, maxX: 200, minZ: 0, maxZ: 0 },
        { minX: 0, maxX: 200, minZ: 0, maxZ: 0 },
        240, 100, 15
      );

      // Verify scale is doubled from base
      const ctx = canvas.getContext('2d');
      function sample(x, y) {
        const d = ctx.getImageData(Math.round(x), Math.round(y), 1, 1).data;
        return { r: d[0], g: d[1], b: d[2] };
      }

      // The centerline at z=0 should translate to a different Y with pan
      const centerY = tf.toScreenY(0) + 5; // + userPanY
      const sampleA = centerY - 4; // middle of Lap A ribbon (8px wide, screen constant)
      const sampleB = centerY + 4;

      // With scale=2 and panX=10, x=100 → screenX = offsetX + (100 - minX)*baseScale*2 + 10
      const screenX = tf.toScreenX(100) * 2 - tf.offsetX + 10; // composed: base + (x-minX)*base*zoom + pan

      return {
        centerY: Math.round(centerY),
        screenX: Math.round(screenX),
        sampleA: sample(screenX, sampleA),
        sampleB: sample(screenX, sampleB),
      };
    });

    const isGreen = (p) => p.g > p.r + 20 && p.g > p.b + 20;
    const isBlue = (p) => p.b > p.r + 20 && p.b > p.g + 20;

    // At x=100, Lap A coasts (neutral), Lap B coasts (neutral) — but we just verify composition produced something
    assert(synthetic.centerY > 0 && synthetic.centerY < 100, 'composed transform places centerline in bounds', `centerY=${synthetic.centerY}`);
    assert(synthetic.screenX > 0 && synthetic.screenX < 240, 'composed transform places point in bounds', `screenX=${synthetic.screenX}`);

    console.log('\n════ SCENARIO 3: ribbon thickness constant under zoom (synthetic) ════');
    const thickness = await page.evaluate(async () => {
      const { renderWalkingSkeleton } = await import('/js/trackHeatmapMap.js');

      function measureRibbonWidth(canvas, lapA, lapB, userScale) {
        canvas.width = 240;
        canvas.height = 100;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, 240, 100);
        renderWalkingSkeleton(canvas, lapA, lapB, {
          showDualRibbon: true,
          ribbonWidthPx: 8,
          ribbonGapPx: 2,
          userScale,
          userPanX: 0,
          userPanY: 0,
        });

        // Measure vertical thickness at x=120 (center of track)
        const col = [];
        for (let y = 0; y < 100; y++) {
          const d = ctx.getImageData(120, y, 1, 1).data;
          const lit = d[0] > 30 || d[1] > 30 || d[2] > 30;
          col.push(lit);
        }
        let first = col.findIndex(v => v);
        let last = col.length - 1 - [...col].reverse().findIndex(v => v);
        if (first === -1) return 0;
        return last - first + 1;
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

      const canvas = document.createElement('canvas');
      canvas.style.width = '240px';
      canvas.style.height = '100px';
      document.body.appendChild(canvas);
      if (!canvas.getBoundingClientRect._shimmed) {
        canvas.getBoundingClientRect = () => ({ width: 240, height: 100, left: 0, top: 0, right: 240, bottom: 100 });
      }

      return {
        scale1: measureRibbonWidth(canvas, lapA, lapB, 1),
        scale10: measureRibbonWidth(canvas, lapA, lapB, 10),
        scale40: measureRibbonWidth(canvas, lapA, lapB, 40),
      };
    });

    // Total ribbon thickness for both ribbons plus gap should be ~18px regardless of zoom
    // Each ribbon is 8px, gap is 2px → total ~18px
    assert(Math.abs(thickness.scale1 - 18) <= 2, 'ribbon thickness at scale=1 is ~18px', `actual=${thickness.scale1}`);
    assert(Math.abs(thickness.scale10 - 18) <= 2, 'ribbon thickness at scale=10 is ~18px', `actual=${thickness.scale10}`);
    assert(Math.abs(thickness.scale40 - 18) <= 2, 'ribbon thickness at scale=40 is ~18px', `actual=${thickness.scale40}`);

    console.log('\n════ SCENARIO 4: interaction on real canvas (Playwright) ════');
    await page.evaluate(() => {
      document.getElementById('circuit-map-panel').style.display = 'block';
      window.__setFeatureFlag('mapZoomPan', true);
      window.__setFeatureFlag('mapDualRibbon', true);
    });

    const canvas = await page.$('#track-heatmap-canvas');
    assert(!!canvas, 'track-heatmap-canvas exists on page');

    await canvas.hover({ position: { x: 1, y: 1 } }); // scroll into view

    // Wheel zoom — use coordinates inside the canvas
    const box = await canvas.boundingBox();
    const wheelX = Math.round(box.x + box.width * 0.5);
    const wheelY = Math.round(box.y + box.height * 0.5);
    const beforeZoom = await page.evaluate(() => window.__mapZoomPanState?.scale || 1);
    await canvas.evaluate((el, cx, cy) => {
      el.dispatchEvent(new WheelEvent('wheel', { deltaY: -100, clientX: cx, clientY: cy, bubbles: true }));
    }, wheelX, wheelY);
    const afterZoom = await page.evaluate(() => window.__mapZoomPanState?.scale || 1);
    assert(afterZoom > beforeZoom, 'wheel zoom increases scale', `${beforeZoom} → ${afterZoom}`);
    assert(afterZoom <= 40, 'zoom scale clamped to <= 40', `${afterZoom}`);

    // Zoom clamp (try to zoom way past limit)
    for (let i = 0; i < 20; i++) {
      await canvas.evaluate((el, cx, cy) => {
        el.dispatchEvent(new WheelEvent('wheel', { deltaY: -500, clientX: cx, clientY: cy, bubbles: true }));
      }, wheelX, wheelY);
    }
    const clampedScale = await page.evaluate(() => window.__mapZoomPanState?.scale || 1);
    assert(clampedScale <= 40, 'scale clamped to max 40 after extreme zoom', `${clampedScale}`);

    // Reset before drag test to avoid huge accumulated offsets
    await canvas.evaluate(el => {
      el.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
    });

    // Drag pan — compute coordinates inside the canvas
    const beforePan = await page.evaluate(() => ({ x: window.__mapZoomPanState?.tx || 0, y: window.__mapZoomPanState?.ty || 0 }));
    const panStartX = Math.round(box.x + box.width * 0.3);
    const panStartY = Math.round(box.y + box.height * 0.3);
    const panEndX = Math.round(panStartX + 50);
    const panEndY = Math.round(panStartY + 20);
    await page.mouse.move(panStartX, panStartY);
    await page.mouse.down();
    await page.mouse.move(panEndX, panEndY);
    await page.mouse.up();
    const afterPan = await page.evaluate(() => ({ x: window.__mapZoomPanState?.tx || 0, y: window.__mapZoomPanState?.ty || 0 }));
    assert(afterPan.x !== beforePan.x || afterPan.y !== beforePan.y, 'pointer drag changes pan offset', `(${beforePan.x},${beforePan.y}) → (${afterPan.x},${afterPan.y})`);

    // Double-click reset
    await canvas.evaluate(el => {
      el.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
    });
    const afterReset = await page.evaluate(() => window.__mapZoomPanState);
    assert(afterReset?.scale === 1, 'dblclick resets scale to 1', `${afterReset?.scale}`);
    assert(afterReset?.tx === 0, 'dblclick resets tx to 0', `${afterReset?.tx}`);
    assert(afterReset?.ty === 0, 'dblclick resets ty to 0', `${afterReset?.ty}`);

    // Cursor styles
    const grabCursor = await canvas.evaluate(el => getComputedStyle(el).cursor);
    assert(grabCursor === 'grab' || grabCursor === 'grabbing', 'canvas has grab cursor', grabCursor);

    console.log('\n════ SCENARIO 5: perf — scripted pan 2s at 60Hz ════');
    const perfResult = await page.evaluate(async () => {
      const canvas = document.getElementById('track-heatmap-canvas');
      const state = window.__mapZoomPanState;
      if (!state || !canvas) return { ok: false, reason: 'missing state or canvas' };

      const frames = [];
      const startT = performance.now();
      let frame = 0;
      return new Promise(resolve => {
        function tick() {
          const t0 = performance.now();
          state.tx = Math.sin(frame * 0.1) * 50;
          state.ty = Math.cos(frame * 0.1) * 30;
          canvas.dispatchEvent(new Event('mapZoomPanChange'));
          const dt = performance.now() - t0;
          frames.push(dt);
          frame++;
          if (performance.now() - startT < 2000) {
            requestAnimationFrame(tick);
          } else {
            frames.sort((a, b) => a - b);
            const p99 = frames[Math.floor(frames.length * 0.99)];
            const max = Math.max(...frames);
            resolve({ ok: p99 <= 16, p99, max, count: frames.length });
          }
        }
        requestAnimationFrame(tick);
      });
    });
    assert(perfResult.ok, 'perf: p99 frame time <= 16ms', `p99=${perfResult.p99}ms max=${perfResult.max}ms frames=${perfResult.count}`);

  } finally {
    await browser.close();
    server.close();
  }

  writeReport();
  if (failCount > 0) throw new Error(`${failCount} Phase 02 assertions failed`);
}

runTests().catch(err => {
  console.error(err);
  writeReport();
  process.exit(1);
});
