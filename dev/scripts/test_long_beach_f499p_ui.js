// @parallel true
'use strict';
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const ROOT = path.resolve(__dirname, '../..');
const SLUG = 'grand-prix-of-long-beach';
const model = JSON.parse(fs.readFileSync(path.join(ROOT, 'product/data/track-coaching',
  `${SLUG}_ferrari-af-corse-2026-50-lm.json`), 'utf8'));
const REF = path.resolve(ROOT, model.reference_lap.path);
function ok(value, label) {
  console.log(`${value ? '[PASS]' : '[FAIL]'} ${label}`);
  if (!value) throw new Error(label);
}
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
    await page.goto(pathToFileURL(path.join(ROOT, 'product/dist/compare.html')).href);
    // Replay the committed practice reference under the real recording filename.
    // This exercises filename-only track resolution without an untracked session dependency.
    await page.locator('#file-input').setInputFiles({
      name: `session_20261101T175418Z_${SLUG}_lmu_practice.parquet`,
      mimeType: 'application/octet-stream', buffer: fs.readFileSync(REF),
    });
    await page.waitForFunction(() => window.__getSessionKeys?.().length > 0);
    const key = (await page.evaluate(() => window.__getSessionKeys()))[0];
    await page.selectOption('#session-picker', `${key}::0`);
    await page.selectOption('#ref-picker', `${key}::0`);
    await page.locator('#compare-btn').click();
    await page.waitForFunction(() => {
      const c = document.getElementById('track-heatmap-canvas');
      return c && c.style.display !== 'none' && c.width > 0;
    });
    const canvas = page.locator('#track-heatmap-canvas');
    await canvas.hover({ position: { x: 2, y: 2 } });
    const state = await page.evaluate(() => {
      const group = document.querySelector('#static-track-outline [data-static-track-outline]');
      const canvas = document.getElementById('track-heatmap-canvas');
      const image = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height);
      let grey = 0;
      for (let i = 0; i < image.data.length; i += 4) {
        const [r, g, b, a] = image.data.slice(i, i + 4);
        if (Math.abs(r - g) < 15 && Math.abs(g - b) < 15 && r > 30 && r < 120 && a > 10) grey++;
      }
      return {
        name: group?.getAttribute('data-static-track-outline'), grey,
        parts: group?.querySelectorAll('polyline').length,
        points: group?.querySelector('[data-static-outline-part="centerline"]')?.getAttribute('points')?.split(' ').length,
      };
    });
    ok(state.name === 'Grand Prix of Long Beach', `correct outline drawn: ${state.name}`);
    ok(state.parts === 3 && state.points === 500, 'all boundaries and 500-point centerline reach SVG renderer');
    ok(state.grey > 50, `static boundary pixels visible in active canvas (${state.grey})`);
    const out = path.join(ROOT, 'var/test-output/long-beach-f499p');
    fs.mkdirSync(out, { recursive: true });
    await canvas.screenshot({ path: path.join(out, 'outline.png') });
    ok(fs.statSync(path.join(out, 'outline.png')).size > 1000, 'render evidence saved (not a pixel golden)');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(`[FAIL] ${error.stack}`); process.exitCode = 1; });
