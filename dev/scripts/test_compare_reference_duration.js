#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Bug 28 (dist/compare.html surface): the built standalone bundle must show
 * the authoritative telemetry-clock lap time (1:16.304), not the old stale
 * scorer value (1:17.345).
 *
 * Loads product/dist/compare.html (the shipped single-file build), feeds the
 * real Road Atlanta race session and the extracted reference lap, and asserts
 * the fastest lap shown is the telemetry-clock value.
 *
 * Requires Playwright — run with `bash scripts/test-summary.sh --pw`.
 */

const { chromium } = require('playwright');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..', '..');
const DIST = path.join(ROOT, 'product', 'dist');
const RACE = path.join(ROOT, 'sessions', 'session_20261004T164430Z_michelin-raceway-road-atlanta_lmu_race.parquet');
const REF = path.join(ROOT, 'product', 'data', 'reference-laps', 'michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.16.304.parquet');

function assert(cond, message, detail = '') {
  if (!cond) throw new Error(`${message}${detail ? ` — ${detail}` : ''}`);
  console.log(`  PASS ${message}${detail ? ` — ${detail}` : ''}`);
}

async function pickerLabels(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll('#session-picker option')].map((o) => o.textContent.trim()));
}

(async () => {
  const { server, port } = await startServer(DIST);
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${port}/compare.html`);

    await page.locator('#file-input').setInputFiles(RACE);
    await page.waitForFunction(() => window.__getSessionKeys?.().length > 0, { timeout: 20000 });
    let labels = await pickerLabels(page);
    const fastest = labels.find((l) => l.includes('★')) || '';
    assert(/1:16\.304/.test(fastest), 'dist session picker fastest lap is 1:16.304', fastest);
    assert(fastest.includes('lap# 15'), 'dist session picker marks lap# 15 as fastest', fastest);

    // The extracted single-lap reference file resolves via its filename.
    await page.reload();
    await page.locator('#file-input').setInputFiles(REF);
    await page.waitForFunction(() => window.__getSessionKeys?.().length > 0, { timeout: 20000 });
    labels = await pickerLabels(page);
    assert(labels.some((l) => /1:16\.304/.test(l)), 'dist reference picker shows 1:16.304', labels.join(' | '));
  } finally {
    await browser.close();
    server.close();
  }
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
