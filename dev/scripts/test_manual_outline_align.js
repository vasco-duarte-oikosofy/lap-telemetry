#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Manual outline alignment tool — Playwright smoke test.
 *
 * Verifies the standalone alignment tool at dev/tools/manual_outline_align.html
 * can load trajectory and track files, produce a valid aligned outline, and
 * respond to zoom controls.
 *
 * Run: node scripts/test_manual_outline_align.js
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { chromium } = require('playwright');

let pass = 0;
let fail = 0;

function ok(condition, label) {
  if (condition) { pass++; console.log(`  [PASS] ${label}`); }
  else           { fail++; console.log(`  [FAIL] ${label}`); }
}

async function main() {
  const ROOT = path.resolve(__dirname, '..', '..');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'manual-outline-align-'));
  const trajectoryPath = path.join(dir, 'trajectory.json');
  const trackPath = path.join(dir, 'tumftm.json');
  fs.writeFileSync(trajectoryPath, JSON.stringify({
    track_name: 'Smoke Spa',
    trajectories: [{ name: 'reference', points: [{ x: 0, y: 0 }, { x: 50, y: 0 }, { x: 50, y: 25 }] }]
  }));
  fs.writeFileSync(trackPath, JSON.stringify({
    track_name: 'Smoke TUMFTM',
    points: [
      { x: 0, y: 0, w_left: 5, w_right: 6 },
      { x: 50, y: 0, w_left: 5, w_right: 6 },
      { x: 50, y: 25, w_left: 5, w_right: 6 }
    ]
  }));

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));
  await page.goto(`file://${path.join(ROOT, 'dev', 'tools', 'manual_outline_align.html')}`);
  await page.setInputFiles('#reference-file', trajectoryPath);
  await page.setInputFiles('#track-file', trackPath);
  await page.waitForFunction(() => window.__manualAlignSmoke && window.__manualAlignSmoke().trackPoints === 3);

  // ── Export produces valid outline ────────────────────────────────────────
  await page.click('#export-button');
  const exported = await page.$eval('#export-text', el => el.value);
  const parsed = JSON.parse(exported);

  ok(parsed.schema_version === 0, `exported outline schema_version is 0 → ${parsed.schema_version}`);
  ok(parsed.centerline.length === 3, `centerline has 3 points → ${parsed.centerline.length}`);
  ok(parsed.left_boundary.length === 3, `left_boundary has 3 points → ${parsed.left_boundary.length}`);
  ok(parsed.right_boundary.length === 3, `right_boundary has 3 points → ${parsed.right_boundary.length}`);

  let allFinite = true;
  for (const point of parsed.centerline.concat(parsed.left_boundary, parsed.right_boundary)) {
    if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) { allFinite = false; break; }
  }
  ok(allFinite, 'all exported point coordinates are finite');

  const smoke = await page.evaluate(() => window.__manualAlignSmoke());
  ok(smoke.finitePoints === smoke.plottedPoints,
    `all plotted points finite → ${smoke.finitePoints}/${smoke.plottedPoints}`);

  // ── Zoom controls ───────────────────────────────────────────────────────
  await page.fill('#view-zoom-num', '2');
  await page.dispatchEvent('#view-zoom-num', 'input');
  const zoomed = await page.evaluate(() => window.__manualAlignSmoke());
  ok(zoomed.viewScale === 2, `zoom control sets viewScale to 2 → ${zoomed.viewScale}`);

  await page.click('#reset-view-button');
  const reset = await page.evaluate(() => window.__manualAlignSmoke());
  ok(reset.viewScale === 1, `reset restores viewScale to 1 → ${reset.viewScale}`);

  ok(errors.length === 0, `no page errors → ${errors.length}`);

  await browser.close();

  const total = pass + fail;
  console.log(`\n  ${pass}/${total} assertions passed`);
  if (fail > 0) {
    console.log(`  ✗ ${fail} assertion(s) failed`);
    process.exit(1);
  }
  console.log('  ✔ All assertions passed');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});