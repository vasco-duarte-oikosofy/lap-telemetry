/**
 * Phase 01c — Dual Ribbon (side-by-side) Test Suite
 *
 * Run: node scripts/test_01c_dual_ribbon.js
 */

'use strict';

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'product', 'web');
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', '01c-test-report');
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
    '# Phase 01c Test Report',
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
  console.log('═══ Phase 01c — Dual Ribbon Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url);

    console.log('════ SCENARIO 1: dual-ribbon synthetic render ════');
    const render = await page.evaluate(async () => {
      const { renderWalkingSkeleton, fitToView } = await import('/js/trackHeatmapMap.js');
      const canvas = document.createElement('canvas');
      canvas.id = 'phase-01c-render-canvas';
      canvas.style.width = '240px';
      canvas.style.height = '100px';
      document.body.appendChild(canvas);
      if (!canvas.getBoundingClientRect._shimmed) {
        canvas.getBoundingClientRect = () => ({ width: 240, height: 100, left: 0, top: 0, right: 240, bottom: 100 });
      }

      // Horizontal track at z=0 from x=0 to x=200
      // Lap A: brake on left (blue), throttle on right (green)
      const lapA = {
        x: new Float64Array([0, 50, 100, 150, 200]),
        z: new Float64Array([0, 0, 0, 0, 0]),
        throttle: new Float64Array([0, 0, 0, 1, 1]),
        brake: new Float64Array([1, 1, 0, 0, 0]),
        color: '#4fc3f7',
      };
      // Lap B: throttle on left (green), brake on right (blue) — reversed
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
      // Ribbon width 8, gap 2
      // offsetA = -(8+2)/2 = -5  → spans [center-9, center-1]
      // offsetB = +5               → spans [center+1, center+9]
      const sampleA = centerY - 5; // middle of Lap A ribbon
      const sampleB = centerY + 5; // middle of Lap B ribbon
      const sampleGap = centerY;    // center gap

      const ctx = canvas.getContext('2d');
      function sample(x, y) {
        const d = ctx.getImageData(Math.round(x), Math.round(y), 1, 1).data;
        return { r: d[0], g: d[1], b: d[2] };
      }

      return {
        aBrake:    sample(tf.toScreenX(25),  sampleA),
        aThrottle: sample(tf.toScreenX(175), sampleA),
        bThrottle: sample(tf.toScreenX(25),  sampleB),
        bBrake:    sample(tf.toScreenX(175), sampleB),
        gap:       sample(tf.toScreenX(100), sampleGap),
        shot: canvas.toDataURL('image/png'),
      };
    });

    // Blue: b dominant; Green: g dominant
    const isBlue = (p) => p.b > p.r + 30 && p.b > p.g + 30;
    const isGreen = (p) => p.g > p.r + 30 && p.g > p.b + 30;
    const isDark = (p) => p.r < 60 && p.g < 60 && p.b < 60;

    assert(isBlue(render.aBrake),    'Lap A brake zone is brake-blue', JSON.stringify(render.aBrake));
    assert(isGreen(render.aThrottle), 'Lap A throttle zone is throttle-green', JSON.stringify(render.aThrottle));
    assert(isGreen(render.bThrottle), 'Lap B throttle zone is throttle-green', JSON.stringify(render.bThrottle));
    assert(isBlue(render.bBrake),    'Lap B brake zone is brake-blue', JSON.stringify(render.bBrake));
    assert(isDark(render.gap),       'gap between ribbons is dark/background', JSON.stringify(render.gap));

    const png = Buffer.from(render.shot.split(',')[1], 'base64');
    const shotPath = path.join(SHOTS_DIR, 'dual-ribbon-synthetic.png');
    fs.writeFileSync(shotPath, png);
    assert(fs.statSync(shotPath).size > 0, 'dual-ribbon synthetic screenshot written', `${fs.statSync(shotPath).size} bytes`);

    console.log('\n════ SCENARIO 2: dual-ribbon feature flag exposed ════');
    const flags = await page.evaluate(() => Object.keys(window.__features || {}));
    assert(flags.includes('mapDualRibbon'), 'mapDualRibbon feature flag is exposed', flags.join(', '));
  } finally {
    await browser.close();
    server.close();
  }

  writeReport();
  if (failCount > 0) throw new Error(`${failCount} Phase 01c assertions failed`);
}

runTests().catch(err => {
  console.error(err);
  writeReport();
  process.exit(1);
});
