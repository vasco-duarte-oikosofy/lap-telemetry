#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Turn labels on the circuit map (docs/specs/MAP_TURN_NAMES.md).
 *
 * Renders a real session through the app and checks the labels in the live DOM:
 * every turn of the loaded track is labelled, labels sit beside their corner,
 * they never overlap each other, the feature flag removes them, and a track
 * without a `turns` block renders exactly as before.
 */

const { chromium } = require('playwright');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'product', 'web');
// Circuit de Barcelona has a baked `turns` block (14 turns); Spa does not.
// Needs real pos_x_m/pos_z_m geometry (the older dev fixtures store a constant
// position, which collapses the map transform) and two laps, for a track that
// HAS a baked turns block. This fixture is two Silverstone International laps.
const SILVERSTONE = path.join(ROOT, 'dev', 'sessions', 'session_20261031T051245Z_silverstone-international-circuit_lmu_quali_2laps.parquet');
const SPA = path.join(ROOT, 'dev', 'sessions', 'session_20260512T140000Z_spa-francorchamps_lmu.parquet');

let pass = 0;
let fail = 0;
function check(name, cond, detail = '') {
  if (cond) {
    console.log(`  PASS ${name}${detail ? ` — ${detail}` : ''}`);
    pass += 1;
  } else {
    console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ''}`);
    fail += 1;
  }
}

async function loadTrack(page, port, file) {
  await page.goto(`http://127.0.0.1:${port}`);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.locator('#file-input').setInputFiles(file);
  await page.waitForFunction(() => window.__getSessionKeys?.().length > 0, { timeout: 15000 });
  const key = (await page.evaluate(() => window.__getSessionKeys()))[0];
  // Pick two distinct laps from whatever the session actually offers.
  const options = await page.evaluate(() =>
    [...document.querySelectorAll('#session-picker option')].map(o => o.value).filter(Boolean));
  const sessionLap = options[0];
  const refLap = options[1] || options[0];
  await page.selectOption('#session-picker', sessionLap);
  await page.selectOption('#ref-picker', refLap);
  await page.locator('#compare-btn').click();
  await page.locator('#map-mode').selectOption('outline');
  // The map renders as an SVG polyline in outline mode and as canvas segments
  // in heatmap mode, so wait for either.
  await page.waitForFunction(() => {
    const map = document.getElementById('circuit-map-panel');
    const drawn = document.getElementById('track-outline').getAttribute('points') ||
      document.getElementById('track-segments')?.childElementCount;
    return map && map.style.display !== 'none' && drawn;
  }, { timeout: 20000 }).catch(async err => {
    const diag = await page.evaluate(() => ({
      panel: document.getElementById('circuit-map-panel')?.style.display,
      points: (document.getElementById('track-outline')?.getAttribute('points') || '').length,
      labels: document.querySelectorAll('#track-turn-labels .turn-label').length,
      keys: window.__getSessionKeys?.() || [],
      placeholders: [...document.querySelectorAll('.placeholder')].map(p => p.textContent.trim()).filter(Boolean),
    }));
    throw new Error(`map did not render: ${JSON.stringify(diag)}`);
  });
}

// The map is canvas-rendered, so labels are read back from the renderer itself
// (canvas pixels), not from the DOM.
const readLabels = () => page => page.evaluate(async () => {
  const { labels } = await window.__turnLabels();
  const canvas = document.getElementById('track-heatmap-canvas');
  return { labels, view: { width: canvas.getBoundingClientRect().width,
                           height: canvas.getBoundingClientRect().height } };
});

(async () => {
  const { server, port } = await startServer(WEB_DIR);
  const browser = await chromium.launch();
  let page;
  try {
    page = await browser.newPage();
    await loadTrack(page, port, SILVERSTONE);

    const { labels, view } = await readLabels()(page);
    check('labels are drawn for the loaded track', labels.length > 0, `${labels.length} labels`);
    check('label text follows "T<n> <name>" or "T<n>"',
      labels.every(l => /^T\d+(\s|$)/.test(l.text)),
      labels.slice(0, 3).map(l => l.text).join(' | '));

    const bakedTurnCount = await page.evaluate(async () => {
      const { findOutlineByTrackName } = await import('/js/trackOutlineManifest.js');
      return findOutlineByTrackName('Silverstone International Circuit')?.turns?.length ?? 0;
    });
    check('every baked turn is labelled', labels.length === bakedTurnCount,
      `${labels.length} labels vs ${bakedTurnCount} baked turns`);
    check('labels use the expected turn numbers in order',
      labels.map(l => l.text.split(' ')[0]).join(',') ===
        Array.from({ length: bakedTurnCount }, (_, i) => `T${i + 1}`).join(','),
      labels.map(l => l.text.split(' ')[0]).join(','));

    let overlaps = 0;
    for (let i = 0; i < labels.length; i++) {
      for (let j = i + 1; j < labels.length; j++) {
        const a = labels[i], b = labels[j];
        const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
        const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
        if (ox > 0 && oy > 0) overlaps += 1;
      }
    }
    check('no two labels overlap', overlaps === 0, `${overlaps} overlapping pairs`);

    const outside = labels.filter(l =>
      l.x < 0 || l.y < 0 || l.x + l.w > view.width || l.y + l.h > view.height);
    check('every label stays inside the map', outside.length === 0,
      outside.map(l => l.text).join(', '));

    // Adjacency: label box within the approved budget of its own apex.
    const fontSize = labels.length ? await page.evaluate(() =>
      Number((document.getElementById('track-heatmap-canvas').width, 0)) || 0) : 0;
    const adjacency = labels.map(l => {
      const cx = l.x + l.w / 2, cy = l.y + l.h / 2;
      return Math.max(Math.abs(cx - l.apexX) - l.w / 2, Math.abs(cy - l.apexY) - l.h / 2);
    });
    const normalCap = Math.min(2.4 * 8, 0.04 * Math.min(view.width, view.height));
    check('every label sits within the adjacency budget of its apex',
      adjacency.every(d => d <= normalCap + 1.5),
      `worst ${Math.max(...adjacency).toFixed(1)} px vs cap ${normalCap.toFixed(1)} px`);

    // Prove the text is actually painted: bright pixels inside a label rect.
    const painted = await page.evaluate((rects) => {
      const canvas = document.getElementById('track-heatmap-canvas');
      const dpr = window.devicePixelRatio || 1;
      const ctx = canvas.getContext('2d');
      return rects.map(r => {
        const x = Math.max(0, Math.round(r.x * dpr));
        const y = Math.max(0, Math.round(r.y * dpr));
        const w = Math.max(1, Math.round(r.w * dpr));
        const h = Math.max(1, Math.round(r.h * dpr));
        const data = ctx.getImageData(x, y, w, h).data;
        let bright = 0;
        for (let i = 0; i < data.length; i += 4) if (data[i] > 120) bright += 1;
        return bright;
      });
    }, labels.slice(0, 4));
    check('label pixels are on the canvas', painted.every(n => n > 3), `bright px ${painted}`);

    // Feature flag OFF -> nothing drawn. `__setFeatureFlag` only flips state, so
    // force a re-render through the resize path (same as a window resize).
    const forceRender = async () => {
      const box = page.viewportSize();
      await page.setViewportSize({ width: box.width - 20, height: box.height });
      await page.waitForTimeout(200);
      await page.setViewportSize(box);
      await page.waitForTimeout(250);
    };
    await page.evaluate(() => window.__setFeatureFlag('mapTurnLabels', false));
    await forceRender();
    await page.locator('#map-mode').selectOption('speed');
    const afterOff = await page.evaluate(async () => (await window.__turnLabels()).labels.length);
    check('flag off removes every label', afterOff === 0, `${afterOff} labels`);

    // Flag back ON in a heatmap mode: labels still render (they are context).
    await page.evaluate(() => window.__setFeatureFlag('mapTurnLabels', true));
    await forceRender();
    await page.locator('#map-mode').selectOption('brake');
    await page.waitForTimeout(150);
    const inHeatmap = await page.evaluate(async () => (await window.__turnLabels()).labels.length);
    check('labels render in heatmap mode too', inHeatmap > 0, `${inHeatmap} labels`);

    // A track with no turns block must render exactly as before.
    await loadTrack(page, port, SPA);
    const spa = await page.evaluate(async () => (await window.__turnLabels()).labels.length);
    check('track without a turns block draws no labels', spa === 0, `${spa} labels`);
  } finally {
    await browser.close();
    server.close();
  }

  console.log(`\n${pass}/${pass + fail} assertions passed`);
  if (fail > 0) {
    console.log('RESULT: FAIL');
    process.exit(1);
  }
  console.log('RESULT: PASS');
})();
