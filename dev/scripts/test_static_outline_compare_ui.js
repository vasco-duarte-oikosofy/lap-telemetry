#!/usr/bin/env node
'use strict';

const { chromium } = require('playwright');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'web');
const SESSION = path.join(ROOT, 'dev', 'sessions', 'session_20260512T140000Z_spa-francorchamps_lmu.parquet');

function assert(cond, message, detail = '') {
  if (!cond) throw new Error(`${message}${detail ? ` — ${detail}` : ''}`);
  console.log(`  PASS ${message}${detail ? ` — ${detail}` : ''}`);
}

(async () => {
  const { server, port } = await startServer(WEB_DIR);
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${port}`);

    await page.locator('#file-input').setInputFiles(SESSION);
    await page.waitForFunction(() => window.__getSessionKeys?.().length > 0, { timeout: 10000 });

    const key = (await page.evaluate(() => window.__getSessionKeys()))[0];
    await page.selectOption('#session-picker', `${key}::0`);
    await page.selectOption('#ref-picker', `${key}::1`);
    await page.locator('#compare-btn').click();

    await page.waitForFunction(() => {
      const canvas = document.getElementById('track-heatmap-canvas');
      return canvas && canvas.style.display !== 'none' && canvas.width > 0;
    }, { timeout: 10000 });

    // Canvas renderer is active: verify static outline pixels are present underneath
    const canvasState = await page.evaluate(() => {
      const canvas = document.getElementById('track-heatmap-canvas');
      if (!canvas) return { error: 'canvas not found' };
      const ctx = canvas.getContext('2d');
      const w = canvas.width, h = canvas.height;
      if (w === 0 || h === 0) return { error: 'canvas empty' };
      const imageData = ctx.getImageData(0, 0, w, h);
      const data = imageData.data;
      // Look for static outline pixels: rgba(210,210,210,0.28) composited on dark
      // background produces R≈G≈B≈55-65, A≈100. We check for greyish pixels as a proxy.
      let outlinePixels = 0;
      for (let i = 0; i < data.length; i += 4) {
        const r = data[i], g = data[i+1], b = data[i+2], a = data[i+3];
        if (Math.abs(r - g) < 15 && Math.abs(g - b) < 15 && r > 30 && r < 120 && a > 10) {
          outlinePixels++;
        }
      }
      let totalNonTransparent = 0;
      for (let i = 3; i < data.length; i += 4) {
        if (data[i] > 10) totalNonTransparent++;
      }
      return { outlinePixels, totalNonTransparent, canvasWidth: w, canvasHeight: h };
    });

    assert(!canvasState.error, 'canvas is rendered', canvasState.error || 'ok');
    assert(canvasState.canvasWidth > 0, 'canvas has positive width', `${canvasState.canvasWidth}px`);
    assert(canvasState.outlinePixels > 50, 'canvas has static outline pixels from Spa artifact', `${canvasState.outlinePixels} outline pixels among ${canvasState.totalNonTransparent} total`);

    // SVG path: also verify static outline group exists in DOM
    const svgState = await page.evaluate(() => {
      const group = document.getElementById('static-track-outline');
      if (!group) return { exists: false };
      const polylines = group.querySelectorAll('polyline');
      return {
        exists: true,
        polylineCount: polylines.length,
        hasLeft: !!group.querySelector('[data-static-outline-part="left_boundary"]'),
        hasRight: !!group.querySelector('[data-static-outline-part="right_boundary"]'),
        hasCenter: !!group.querySelector('[data-static-outline-part="centerline"]'),
      };
    });
    assert(svgState.exists, 'SVG static-outline group exists in DOM');
    assert(svgState.hasLeft && svgState.hasRight && svgState.hasCenter, 'SVG static outline has boundary/centerline parts', `${svgState.polylineCount} polylines`);
  } finally {
    await browser.close();
    server.close();
  }
})().catch(err => {
  console.error(err);
  process.exit(1);
});

