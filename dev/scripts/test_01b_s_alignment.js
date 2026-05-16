/**
 * Phase 01b — s-based Cross-lap Alignment Test Suite
 *
 * Run: node scripts/test_01b_s_alignment.js
 */

'use strict';

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'web');
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', '01b-test-report');
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
    '# Phase 01b Test Report',
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
  console.log('═══ Phase 01b — s-based Cross-lap Alignment Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url);

    console.log('════ SCENARIO 1: sLookup unit tests ════');
    const unit = await page.evaluate(async () => {
      const { sLookup, assertStrictlyMonotonic } = await import('/js/sLookup.js');

      // Synthetic lap: 10 samples at known distances
      const lap = {
        s: new Float64Array([0, 10, 25, 40, 60, 80, 100, 120, 150, 200]),
        x: new Float64Array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
        z: new Float64Array([0, 10, 20, 30, 40, 50, 60, 70, 80, 90]),
        speed: new Float64Array([0, 20, 40, 60, 80, 100, 120, 140, 160, 200]),
      };

      const exact0 = sLookup(lap, 0);
      const exact25 = sLookup(lap, 25);
      const exact200 = sLookup(lap, 200);
      const mid = sLookup(lap, 50); // between 40 and 60 → frac = 0.5 → x=3.5, z=35, speed=70
      const mid2 = sLookup(lap, 32.5); // between 25 and 40 → frac = 0.5 → x=2.5, z=25, speed=50

      // Monotonicity: ascending s queries → ascending x
      const mono = [];
      for (let target = 0; target <= 200; target += 5) {
        const res = sLookup(lap, target);
        mono.push({ s: target, x: res.x });
      }
      const isMonotonic = mono.every((v, i) => i === 0 || v.x >= mono[i - 1].x);

      // Random property: 20 random queries, interpolated s within epsilon
      const EPS = 1e-9;
      let propOk = true;
      let worst = 0;
      for (let i = 0; i < 20; i++) {
        const target = Math.random() * 200;
        const res = sLookup(lap, target);
        const diff = Math.abs(res.s - target);
        if (diff > EPS) { propOk = false; worst = Math.max(worst, diff); }
      }

      return {
        exact0,
        exact25,
        exact200,
        mid,
        mid2,
        isMonotonic,
        monoLength: mono.length,
        propOk,
        worst,
      };
    });

    assert(unit.exact0.x === 0 && unit.exact0.speed === 0, 'sLookup at start returns exact sample', JSON.stringify(unit.exact0));
    assert(unit.exact25.x === 2 && unit.exact25.speed === 40, 'sLookup at exact middle sample returns exact sample', JSON.stringify(unit.exact25));
    assert(unit.exact200.x === 9 && unit.exact200.speed === 200, 'sLookup at end returns exact sample', JSON.stringify(unit.exact200));
    assert(Math.abs(unit.mid.x - 3.5) < 1e-9 && Math.abs(unit.mid.z - 35) < 1e-9 && Math.abs(unit.mid.speed - 70) < 1e-9,
           'sLookup interpolates mid-point correctly', JSON.stringify(unit.mid));
    assert(Math.abs(unit.mid2.x - 2.5) < 1e-9 && Math.abs(unit.mid2.z - 25) < 1e-9 && Math.abs(unit.mid2.speed - 50) < 1e-9,
           'sLookup interpolates another mid-point correctly', JSON.stringify(unit.mid2));
    assert(unit.isMonotonic, 'sLookup is monotonic (ascending s → ascending x)');
    assert(unit.monoLength === 41, 'monotonicity check covers 41 positions', String(unit.monoLength));
    assert(unit.propOk, 'sLookup random property: interpolated s within epsilon', `worst diff ${unit.worst}`);

    console.log('\n════ SCENARIO 2: monotonicity assertion fires on corrupted data ════');
    const devEx = await page.evaluate(async () => {
      const { assertStrictlyMonotonic } = await import('/js/sLookup.js');
      const bad = new Float64Array([0, 10, 20, 15, 30, 40]);
      try {
        assertStrictlyMonotonic(bad, 'test_s');
        return { threw: false, msg: '' };
      } catch (e) {
        return { threw: true, msg: e.message };
      }
    });
    assert(devEx.threw, 'monotonicity assertion throws on non-monotonic data', devEx.msg);
    assert(devEx.msg.includes('index 3'), 'assertion message contains violation index', devEx.msg);

    // Also verify good data passes without throwing
    const goodEx = await page.evaluate(async () => {
      const { assertStrictlyMonotonic } = await import('/js/sLookup.js');
      const good = new Float64Array([0, 10, 20, 30, 40]);
      try {
        assertStrictlyMonotonic(good, 'good_s');
        return { threw: false };
      } catch (e) {
        return { threw: true, msg: e.message };
      }
    });
    assert(!goodEx.threw, 'monotonicity assertion passes on strictly monotonic data');

    console.log('\n════ SCENARIO 3: debug tick render test ════');
    const render = await page.evaluate(async () => {
      const { renderWalkingSkeleton } = await import('/js/trackHeatmapMap.js');
      const canvas = document.createElement('canvas');
      canvas.id = 'phase-01b-render-canvas';
      canvas.style.width = '240px';
      canvas.style.height = '100px';
      document.body.appendChild(canvas);
      // getBoundingClientRect already shimmed by test harness (from 01a test)
      if (!canvas.getBoundingClientRect._shimmed) {
        canvas.getBoundingClientRect = () => ({ width: 240, height: 100, left: 0, top: 0, right: 240, bottom: 100 });
      }

      const lapA = {
        x: new Float64Array([0, 50, 100, 150, 200]),
        z: new Float64Array([0, 0, 0, 0, 0]),
        throttle: new Float64Array([0, 0, 0, 1, 1]),
        brake: new Float64Array([1, 1, 0, 0, 0]),
        color: '#4fc3f7',
        raw: {
          s: new Float64Array([0, 50, 100, 150, 200]),
          x: new Float64Array([0, 50, 100, 150, 200]),
          z: new Float64Array([0, 0, 0, 0, 0]),
        },
      };
      const lapB = {
        x: new Float64Array([0, 200]),
        z: new Float64Array([20, 20]),
        color: '#ff9800',
        raw: {
          s: new Float64Array([0, 200]),
          x: new Float64Array([0, 200]),
          z: new Float64Array([20, 20]),
        },
      };
      renderWalkingSkeleton(canvas, lapA, lapB, { showSAlignmentDebug: true });

      const ctx = canvas.getContext('2d');
      // Sample near where a tick at s=100 on lapA should be (screen x ~ 135, y ~ 50)
      // For the test we just check that some white pixels appear in the canvas
      const data = ctx.getImageData(0, 0, 240, 100).data;
      let whiteCount = 0;
      for (let i = 0; i < data.length; i += 4) {
        if (data[i] > 200 && data[i + 1] > 200 && data[i + 2] > 200) whiteCount++;
      }
      return {
        whiteCount,
        shot: canvas.toDataURL('image/png'),
      };
    });
    assert(render.whiteCount > 0, 'debug ticks render white pixels on canvas', `whiteCount=${render.whiteCount}`);

    const png = Buffer.from(render.shot.split(',')[1], 'base64');
    const shotPath = path.join(SHOTS_DIR, 'alignment-debug-ticks.png');
    fs.writeFileSync(shotPath, png);
    assert(fs.statSync(shotPath).size > 0, 'sAlignment debug screenshot artifact written', `${fs.statSync(shotPath).size} bytes`);

  } finally {
    await browser.close();
    server.close();
  }

  writeReport();
  if (failCount > 0) throw new Error(`${failCount} Phase 01b assertions failed`);
}

runTests().catch(err => {
  console.error(err);
  writeReport();
  process.exit(1);
});
