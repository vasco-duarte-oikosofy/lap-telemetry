/**
 * Phase 04 — Hover Crosshair and Per-Lap Readout Test Suite
 *
 * Run: node scripts/test_04_hover.js
 */
// @parallel true

'use strict';

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'product', 'web');
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', '04-test-report');
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
    '# Phase 04 Test Report',
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
  console.log('═══ Phase 04 — Hover Crosshair and Per-Lap Readout Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url);

    console.log('════ SCENARIO 1: feature flag exposed ════');
    const flags = await page.evaluate(() => Object.keys(window.__features || {}));
    assert(flags.includes('mapHover'), 'mapHover feature flag is exposed', flags.join(', '));

    console.log('\n════ SCENARIO 2: hover readout appears with correct values ════');
    const synthetic = await page.evaluate(async () => {
      const { renderWalkingSkeleton, fitToView, getLastTransform } = await import('/js/trackHeatmapMap.js');
      const { createMapHover } = await import('/js/mapHover.js');

      // Create a dedicated synthetic canvas positioned at (0,0) so
      // getBoundingClientRect is deterministic without shimming.
      const canvas = document.createElement('canvas');
      canvas.id = 'phase-04-hover-canvas';
      canvas.style.cssText = 'position:absolute;left:0;top:0;width:400px;height:200px;';
      document.body.appendChild(canvas);

      // Horizontal track at z=0 from x=0 to x=200; s aligns with x
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
          throttle: new Float64Array([0, 0, 0, 1, 1]),
          brake: new Float64Array([1, 1, 0, 0, 0]),
        },
      };
      const lapB = {
        x: new Float64Array([0, 50, 100, 150, 200]),
        z: new Float64Array([0, 0, 0, 0, 0]),
        throttle: new Float64Array([1, 1, 0, 0, 0]),
        brake: new Float64Array([0, 0, 0, 1, 1]),
        color: '#ff9800',
        raw: {
          s: new Float64Array([0, 50, 100, 150, 200]),
          x: new Float64Array([0, 50, 100, 150, 200]),
          z: new Float64Array([0, 0, 0, 0, 0]),
          throttle: new Float64Array([1, 1, 0, 0, 0]),
          brake: new Float64Array([0, 0, 0, 1, 1]),
        },
      };

      renderWalkingSkeleton(canvas, lapA, lapB, {
        showDualRibbon: true,
        showHover: true,
        ribbonWidthPx: 8,
        ribbonGapPx: 2,
      });

      const mapHover = createMapHover(canvas, () => ({
        lapA,
        lapB,
        transform: getLastTransform(),
      }), () => {
        renderWalkingSkeleton(canvas, lapA, lapB, {
          showDualRibbon: true,
          showHover: true,
          hoverState: mapHover.getState(),
          ribbonWidthPx: 8,
          ribbonGapPx: 2,
        });
      });
      mapHover.rebuild();
      window.__testMapHover = mapHover;

      // Compute screen coordinates for world (100, 0)
      const tf = fitToView(
        { minX: 0, maxX: 200, minZ: 0, maxZ: 0 },
        { minX: 0, maxX: 200, minZ: 0, maxZ: 0 },
        400, 200, 15
      );
      return {
        screenX: Math.round(tf.toScreenX(100)),
        screenY: Math.round(tf.toScreenY(0)),
      };
    });

    // Dispatch pointermove at the known screen position (canvas is at 0,0)
    const hoverX = synthetic.screenX;
    const hoverY = synthetic.screenY;
    await page.evaluate(({ x, y }) => {
      const canvas = document.getElementById('phase-04-hover-canvas');
      canvas.dispatchEvent(new PointerEvent('pointermove', {
        clientX: x, clientY: y, bubbles: true, pointerType: 'mouse'
      }));
    }, { x: hoverX, y: hoverY });
    await page.waitForTimeout(50);

    const readout = await page.$('#map-hover-readout');
    assert(!!readout, 'hover readout exists in DOM');

    const readoutVisible = await page.evaluate(() => {
      const el = document.getElementById('map-hover-readout');
      return el && getComputedStyle(el).display !== 'none';
    });
    assert(readoutVisible, 'hover readout is visible after pointermove');

    const readoutText = await page.evaluate(() => {
      const el = document.getElementById('map-hover-readout');
      return el ? el.textContent : '';
    });
    console.log(`  readout text: ${readoutText}`);
    assert(readoutText.includes('Distance:'), 'readout shows distance');
    assert(readoutText.includes('Lap A'), 'readout shows Lap A label');
    assert(readoutText.includes('Lap B'), 'readout shows Lap B label');
    // At s=100, both laps have throttle=0 brake=0 in the fixture
    assert(readoutText.includes('Throttle 0%'), 'readout shows throttle 0%');
    assert(readoutText.includes('Brake 0%'), 'readout shows brake 0%');

    console.log('\n════ SCENARIO 2b: linked chart hover reuses mapHover readout ════');
    const linkedHover = await page.evaluate(({ x, y }) => {
      const canvas = document.getElementById('phase-04-hover-canvas');
      const mapHover = window.__testMapHover;
      const hasApi = !!mapHover?.setLinkedDistance && !!mapHover?.clearLinkedDistance;
      if (!hasApi) return { hasApi };

      // While direct pointer hover is active at s=100, linked hover must not replace it.
      mapHover.setLinkedDistance(150);
      let text = document.getElementById('map-hover-readout')?.textContent || '';
      const directStillWins = text.includes('Distance: 100 m');

      // Once the pointer leaves the map, the stored linked distance should drive
      // the same readout UI at s=150.
      canvas.dispatchEvent(new PointerEvent('pointerleave', {
        clientX: x, clientY: y, bubbles: true, pointerType: 'mouse'
      }));
      text = document.getElementById('map-hover-readout')?.textContent || '';
      const state = mapHover.getState();

      mapHover.clearLinkedDistance();
      const hiddenAfterClear = getComputedStyle(document.getElementById('map-hover-readout')).display === 'none';

      return {
        hasApi,
        directStillWins,
        linkedText: text,
        linkedDistance: Math.round(state?.s ?? -1),
        hiddenAfterClear,
      };
    }, { x: hoverX, y: hoverY });

    assert(linkedHover.hasApi, 'mapHover exposes linked-distance API');
    assert(linkedHover.directStillWins, 'direct map hover wins over linked hover');
    console.log(`  linked readout text: ${linkedHover.linkedText}`);
    assert(linkedHover.linkedDistance === 150, 'linked hover state uses chart distance', `${linkedHover.linkedDistance} m`);
    assert(linkedHover.linkedText.includes('Distance: 150 m'), 'linked hover readout shows chart distance');
    assert(linkedHover.linkedText.includes('Throttle 100%'), 'linked hover readout uses same Lap A throttle UI');
    assert(linkedHover.linkedText.includes('Brake 100%'), 'linked hover readout uses same Lap B brake UI');
    assert(linkedHover.hiddenAfterClear, 'linked hover clear hides readout');

    // Restore direct hover for the tick geometry assertions.
    await page.evaluate(({ x, y }) => {
      const canvas = document.getElementById('phase-04-hover-canvas');
      canvas.dispatchEvent(new PointerEvent('pointermove', {
        clientX: x, clientY: y, bubbles: true, pointerType: 'mouse'
      }));
    }, { x: hoverX, y: hoverY });
    await page.waitForTimeout(50);

    console.log('\n════ SCENARIO 3: perpendicular tick geometry ════');
    const tickPixels = await page.evaluate(() => {
      const canvas = document.getElementById('phase-04-hover-canvas');
      const ctx = canvas.getContext('2d');
      const tf = canvas.__lastTf;
      // Recompute since we stored it on canvas for convenience
      const { fitToView } = window.__testFitToView || { fitToView: () => ({ toScreenX: x=>x, toScreenY: z=>z }) };
      const sx = Math.round(100); // approximate; better: sample from known render
      const sy = Math.round(100);

      // Just sample the actual canvas at the hover position
      const mapHover = window.__testMapHover;
      const state = mapHover ? mapHover.getState() : null;
      if (!state) return { vertical: [], horizontal: [], sx: 0, sy: 0 };

      const hx = Math.round(state.screenX || 0);
      const hy = Math.round(state.screenY || 0);

      function sample(x, y) {
        const d = ctx.getImageData(Math.round(x), Math.round(y), 1, 1).data;
        return { r: d[0], g: d[1], b: d[2] };
      }

      const vertical = [];
      for (let dy = -15; dy <= 15; dy++) vertical.push(sample(hx, hy + dy));
      const horizontal = [];
      for (let dx = -8; dx <= 8; dx++) horizontal.push(sample(hx + dx, hy));

      return { vertical, horizontal, sx: hx, sy: hy };
    });

    console.log(`  tick screen pos: ${tickPixels.sx}, ${tickPixels.sy}`);

    const isWhiteish = (p) => p.r > 200 && p.g > 200 && p.b > 200;
    const verticalWhiteCount = tickPixels.vertical.filter(isWhiteish).length;
    const horizontalWhiteCount = tickPixels.horizontal.filter(isWhiteish).length;

    assert(verticalWhiteCount >= 5, 'tick has white pixels along vertical line',
      `${verticalWhiteCount} white-ish pixels`);
    assert(horizontalWhiteCount <= 3, 'tick is ~1px wide horizontally',
      `${horizontalWhiteCount} white-ish pixels`);

    console.log('\n════ SCENARIO 4: readout hidden during pointer drag ════');
    // Use the synthetic canvas for drag test
    await page.evaluate(({ x, y }) => {
      const canvas = document.getElementById('phase-04-hover-canvas');
      canvas.dispatchEvent(new PointerEvent('pointerdown', {
        clientX: x, clientY: y, bubbles: true, pointerType: 'mouse', isPrimary: true
      }));
      canvas.dispatchEvent(new PointerEvent('pointermove', {
        clientX: x + 30, clientY: y + 20, bubbles: true, pointerType: 'mouse', isPrimary: true
      }));
    }, { x: hoverX, y: hoverY });
    await page.waitForTimeout(50);

    const readoutHiddenDuringDrag = await page.evaluate(() => {
      const el = document.getElementById('map-hover-readout');
      return !el || getComputedStyle(el).display === 'none';
    });
    assert(readoutHiddenDuringDrag, 'readout is hidden during pointer drag');

    // End drag and move slightly to re-trigger hover
    await page.evaluate(({ x, y }) => {
      const canvas = document.getElementById('phase-04-hover-canvas');
      canvas.dispatchEvent(new PointerEvent('pointerup', {
        clientX: x + 30, clientY: y + 20, bubbles: true, pointerType: 'mouse', isPrimary: true
      }));
      canvas.dispatchEvent(new PointerEvent('pointermove', {
        clientX: x + 31, clientY: y + 21, bubbles: true, pointerType: 'mouse', isPrimary: true
      }));
    }, { x: hoverX, y: hoverY });
    await page.waitForTimeout(50);

    const readoutReappears = await page.evaluate(() => {
      const el = document.getElementById('map-hover-readout');
      return el && getComputedStyle(el).display !== 'none';
    });
    assert(readoutReappears, 'readout reappears after drag ends');

    console.log('\n════ SCENARIO 5: readout flips near canvas edges ════');
    // Hover near bottom-right corner of the 400x200 canvas
    const nearRightX = 390;
    const nearBottomY = 190;
    await page.evaluate(({ x, y }) => {
      const canvas = document.getElementById('phase-04-hover-canvas');
      canvas.dispatchEvent(new PointerEvent('pointermove', {
        clientX: x, clientY: y, bubbles: true, pointerType: 'mouse'
      }));
    }, { x: nearRightX, y: nearBottomY });
    await page.waitForTimeout(50);

    const flipStyles = await page.evaluate(() => {
      const el = document.getElementById('map-hover-readout');
      if (!el) return null;
      const s = el.style;
      return { left: s.left, top: s.top };
    });
    console.log(`  flip styles: left=${flipStyles?.left}, top=${flipStyles?.top}`);

    assert(flipStyles && parseInt(flipStyles.left) < nearRightX,
      'readout flips horizontally near right edge',
      `left=${flipStyles?.left}`);
    assert(flipStyles && parseInt(flipStyles.top) < nearBottomY,
      'readout flips vertically near bottom edge',
      `top=${flipStyles?.top}`);

    // Screenshot artifact
    const png = await page.screenshot({ path: path.join(SHOTS_DIR, 'phase-04-page.png') });
    assert(png.length > 0, 'phase-04 page screenshot written', `${png.length} bytes`);

  } finally {
    await browser.close();
    server.close();
  }

  writeReport();
  if (failCount > 0) throw new Error(`${failCount} Phase 04 assertions failed`);
}

runTests().catch(err => {
  console.error(err);
  writeReport();
  process.exit(1);
});
