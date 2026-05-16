/**
 * Phase 01a — Heatmap Ribbon, Single Lap Test Suite
 *
 * Run: node scripts/test_01a_heatmap_single_lap.js
 */
// @parallel true

'use strict';

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'product', 'web');
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', '01a-test-report');
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
    '# Phase 01a Test Report',
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
  console.log('═══ Phase 01a — Heatmap Ribbon, Single Lap Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url);

    console.log('════ SCENARIO 1: color ramp unit tests ════');
    const unit = await page.evaluate(async () => {
      const { colorForNet, NET_COLOR_LUT } = await import('/js/colorRamp.js');

      function hexToRgb(hex) {
        const n = Number.parseInt(hex.slice(1), 16);
        return [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(v => v / 255);
      }
      function srgbToLinear(c) {
        return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      }
      function rgbToOklab(hex) {
        const [r, g, b] = hexToRgb(hex).map(srgbToLinear);
        const l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b;
        const m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b;
        const s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b;
        const l_ = Math.cbrt(l), m_ = Math.cbrt(m), s_ = Math.cbrt(s);
        return [
          0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
          1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
          0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
        ];
      }
      function dist(a, b) {
        const aa = rgbToOklab(a), bb = rgbToOklab(b);
        return Math.hypot(aa[0] - bb[0], aa[1] - bb[1], aa[2] - bb[2]);
      }
      function channelDelta(a, b) {
        const ar = hexToRgb(a).map(v => Math.round(v * 255));
        const br = hexToRgb(b).map(v => Math.round(v * 255));
        return Math.max(...ar.map((v, i) => Math.abs(v - br[i])));
      }

      const endpoints = {
        brake: colorForNet(-1),
        neutral: colorForNet(0),
        throttle: colorForNet(1),
      };
      const midBrake = colorForNet(-0.5);
      const midThrottle = colorForNet(0.5);
      const lutMismatches = [];
      for (let i = 0; i < NET_COLOR_LUT.length; i++) {
        const net = -1 + (2 * i) / 255;
        const delta = channelDelta(NET_COLOR_LUT[i], colorForNet(net));
        if (delta > 1) lutMismatches.push({ i, delta, lut: NET_COLOR_LUT[i], direct: colorForNet(net) });
      }
      return {
        endpoints,
        midBrake,
        midThrottle,
        midBrakeToBrake: dist(midBrake, endpoints.brake),
        midBrakeToNeutral: dist(midBrake, endpoints.neutral),
        midThrottleToThrottle: dist(midThrottle, endpoints.throttle),
        midThrottleToNeutral: dist(midThrottle, endpoints.neutral),
        lutLength: NET_COLOR_LUT.length,
        lutMismatches,
      };
    });

    assert(unit.endpoints.brake === '#0a3d91', 'colorForNet(-1) exact endpoint', unit.endpoints.brake);
    assert(unit.endpoints.neutral === '#2a3340', 'colorForNet(0) exact endpoint', unit.endpoints.neutral);
    assert(unit.endpoints.throttle === '#0f7a2e', 'colorForNet(1) exact endpoint', unit.endpoints.throttle);
    assert(unit.midBrakeToBrake < unit.midBrakeToNeutral, 'colorForNet(-0.5) closer to brake endpoint than neutral', `${unit.midBrake} distances ${unit.midBrakeToBrake.toFixed(4)} < ${unit.midBrakeToNeutral.toFixed(4)}`);
    assert(unit.midThrottleToThrottle < unit.midThrottleToNeutral, 'colorForNet(0.5) closer to throttle endpoint than neutral', `${unit.midThrottle} distances ${unit.midThrottleToThrottle.toFixed(4)} < ${unit.midThrottleToNeutral.toFixed(4)}`);
    assert(unit.lutLength === 256, 'net color LUT has 256 entries', String(unit.lutLength));
    assert(unit.lutMismatches.length === 0, 'LUT matches colorForNet at integer positions', JSON.stringify(unit.lutMismatches.slice(0, 3)));

    console.log('\n════ SCENARIO 2: ribbon render colors ════');
    const render = await page.evaluate(async () => {
      const { renderWalkingSkeleton, fitToView } = await import('/js/trackHeatmapMap.js');
      const canvas = document.createElement('canvas');
      canvas.id = 'phase-01a-render-canvas';
      canvas.style.width = '240px';
      canvas.style.height = '100px';
      document.body.appendChild(canvas);
      canvas.getBoundingClientRect = () => ({ width: 240, height: 100, left: 0, top: 0, right: 240, bottom: 100 });

      const lapA = {
        x: new Float64Array([0, 50, 100, 150, 200]),
        z: new Float64Array([0, 0, 0, 0, 0]),
        throttle: new Float64Array([0, 0, 0, 1, 1]),
        brake: new Float64Array([1, 1, 0, 0, 0]),
        color: '#4fc3f7',
      };
      const lapB = {
        x: new Float64Array([0, 200]),
        z: new Float64Array([20, 20]),
        color: '#ff9800',
      };
      renderWalkingSkeleton(canvas, lapA, lapB, { showHeatmapSingleLap: true, ribbonWidthPx: 12 });

      const transform = fitToView({ minX: 0, maxX: 200, minZ: 0, maxZ: 0 }, { minX: 0, maxX: 200, minZ: 20, maxZ: 20 }, 240, 100, 15);
      const ctx = canvas.getContext('2d');
      function sample(x, z) {
        const data = ctx.getImageData(Math.round(transform.toScreenX(x)), Math.round(transform.toScreenY(z)), 1, 1).data;
        return { r: data[0], g: data[1], b: data[2], a: data[3] };
      }
      return {
        brakePixel: sample(50, 0),
        throttlePixel: sample(175, 0),
        shot: canvas.toDataURL('image/png'),
      };
    });

    const brakeBlue = render.brakePixel.b > render.brakePixel.r && render.brakePixel.b > render.brakePixel.g;
    const throttleGreen = render.throttlePixel.g > render.throttlePixel.r && render.throttlePixel.g > render.throttlePixel.b;
    assert(brakeBlue, 'braking-zone pixel is brake-blue', JSON.stringify(render.brakePixel));
    assert(throttleGreen, 'throttle-zone pixel is throttle-green', JSON.stringify(render.throttlePixel));

    const png = Buffer.from(render.shot.split(',')[1], 'base64');
    const shotPath = path.join(SHOTS_DIR, 'synthetic-ribbon.png');
    fs.writeFileSync(shotPath, png);
    assert(fs.statSync(shotPath).size > 0, 'synthetic ribbon screenshot artifact written', `${fs.statSync(shotPath).size} bytes`);
  } finally {
    await browser.close();
    server.close();
  }

  writeReport();
  if (failCount > 0) throw new Error(`${failCount} Phase 01a assertions failed`);
}

runTests().catch(err => {
  console.error(err);
  writeReport();
  process.exit(1);
});
