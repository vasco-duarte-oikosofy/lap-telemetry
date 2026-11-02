// @parallel true
'use strict';
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const ROOT = path.resolve(__dirname, '../..');
function ok(value, label) {
  console.log(`${value ? '[PASS]' : '[FAIL]'} ${label}`);
  if (!value) throw new Error(label);
}
(async () => {
  ok(fs.readFileSync(path.join(ROOT, 'product/dist/compare.html'), 'utf8').split(/\r?\n/).length <= 437,
    'rebuilt standalone artifact respects the 437-line ceiling');
  const model = JSON.parse(fs.readFileSync(path.join(ROOT,
    'product/data/track-coaching/paul-ricard---1a_dkr-engineering-4-elms25.json'), 'utf8'));
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
    await page.addInitScript(() => {
      window.__paintedTurns = [];
      const original = CanvasRenderingContext2D.prototype.fillText;
      CanvasRenderingContext2D.prototype.fillText = function(text, ...args) {
        if (/^T\d+(?:\s|$)/.test(String(text))) {
          if (/^T1(?:\s|$)/.test(String(text))) window.__paintedTurns = [];
          window.__paintedTurns.push(String(text));
        }
        return original.call(this, text, ...args);
      };
    });
    await page.goto(pathToFileURL(path.join(ROOT, 'product/dist/compare.html')).href);
    await page.locator('#file-input').setInputFiles({
      name: 'session_20261101T190458Z_paul-ricard---1a_lmu_race.parquet',
      mimeType: 'application/octet-stream', buffer: fs.readFileSync(path.resolve(ROOT, model.reference_lap.path)),
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
      const g = document.querySelector('#static-track-outline [data-static-track-outline]');
      const c = document.getElementById('track-heatmap-canvas');
      const pixels = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      let grey = 0;
      for (let i = 0; i < pixels.length; i += 4) {
        if (Math.abs(pixels[i]-pixels[i+1]) < 15 && Math.abs(pixels[i+1]-pixels[i+2]) < 15 &&
            pixels[i] > 30 && pixels[i] < 120 && pixels[i+3] > 10) grey++;
      }
      return { name: g?.getAttribute('data-static-track-outline'),
        parts: g?.querySelectorAll('polyline').length, grey, labels: window.__paintedTurns };
    });
    ok(state.name === 'Paul Ricard - 1A', `standalone file replay draws exact 1A layout: ${state.name}`);
    ok(state.parts === 3 && state.grey > 50, `all outline parts reach active canvas (${state.grey} boundary pixels)`);
    ok(state.labels.length === 14, `all 14 official/subdivided zones painted: ${state.labels.join(', ')}`);
    ok(state.labels.some(t => t.includes('Garlaban')) && state.labels.some(t => t.includes('Lac')),
      'correct official Garlaban/Lac names are painted, not legacy shortcut/Tour labels');
    const out = path.join(ROOT, 'var/test-output/paul-ricard-1a');
    fs.mkdirSync(out, { recursive: true });
    await canvas.screenshot({ path: path.join(out, 'outline.png') });
    ok(fs.statSync(path.join(out, 'outline.png')).size > 1000, 'actual renderer evidence saved (not a pixel golden)');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(`[FAIL] ${error.stack}`); process.exitCode = 1; });
