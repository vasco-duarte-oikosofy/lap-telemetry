#!/usr/bin/env node
'use strict';

const { chromium } = require('playwright');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..');
const WEB_DIR = path.join(ROOT, 'web');
const SESSION = path.join(ROOT, 'sessions', 'session_20260512T140000Z_spa-francorchamps_lmu.parquet');

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
      const group = document.querySelector('#static-track-outline [data-static-track-outline="spa-francorchamps"]');
      return group && group.querySelectorAll('polyline').length === 3;
    }, { timeout: 10000 });

    const state = await page.evaluate(() => {
      const svg = document.getElementById('circuit-map-svg');
      const staticGroup = document.getElementById('static-track-outline');
      const trackSegments = document.getElementById('track-segments');
      const trackOutline = document.getElementById('track-outline');
      const parts = [...staticGroup.querySelectorAll('polyline')].map(p => ({
        part: p.getAttribute('data-static-outline-part'),
        pointCount: (p.getAttribute('points') || '').trim().split(/\s+/).filter(Boolean).length,
      }));
      return {
        childOrder: [...svg.children].map(el => el.id),
        trackPoints: (trackOutline.getAttribute('points') || '').trim().split(/\s+/).filter(Boolean).length,
        parts,
        staticBeforeSegments: [...svg.children].indexOf(staticGroup) < [...svg.children].indexOf(trackSegments),
        staticBeforeTrajectory: [...svg.children].indexOf(staticGroup) < [...svg.children].indexOf(trackOutline),
      };
    });

    assert(state.staticBeforeSegments, 'static outline group renders behind heatmap segments', state.childOrder.join(' > '));
    assert(state.staticBeforeTrajectory, 'static outline group renders behind trajectory outline', state.childOrder.join(' > '));
    assert(state.trackPoints > 200, 'existing trajectory outline still renders', `points=${state.trackPoints}`);
    for (const part of ['left_boundary', 'right_boundary', 'centerline']) {
      const found = state.parts.find(p => p.part === part);
      assert(found && found.pointCount > 1000, `${part} renders from Spa static artifact`, `points=${found?.pointCount || 0}`);
    }
  } finally {
    await browser.close();
    server.close();
  }
})().catch(err => {
  console.error(err);
  process.exit(1);
});
