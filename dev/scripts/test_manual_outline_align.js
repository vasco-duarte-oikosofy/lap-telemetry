#!/usr/bin/env node
'use strict';
// @parallel true

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { chromium } = require('playwright');

async function main() {
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
  await page.goto(`file://${path.resolve('tools/manual_outline_align.html')}`);
  await page.setInputFiles('#reference-file', trajectoryPath);
  await page.setInputFiles('#track-file', trackPath);
  await page.waitForFunction(() => window.__manualAlignSmoke && window.__manualAlignSmoke().trackPoints === 3);
  await page.click('#export-button');
  const exported = await page.$eval('#export-text', el => el.value);
  const parsed = JSON.parse(exported);
  assert.equal(parsed.schema_version, 0);
  assert.equal(parsed.centerline.length, 3);
  assert.equal(parsed.left_boundary.length, 3);
  assert.equal(parsed.right_boundary.length, 3);
  for (const point of parsed.centerline.concat(parsed.left_boundary, parsed.right_boundary)) {
    assert(Number.isFinite(point.x) && Number.isFinite(point.y), 'exported point coordinates are finite');
  }
  const smoke = await page.evaluate(() => window.__manualAlignSmoke());
  assert.equal(smoke.finitePoints, smoke.plottedPoints, 'all plotted points are finite');
  await page.fill('#view-zoom-num', '2');
  await page.dispatchEvent('#view-zoom-num', 'input');
  const zoomed = await page.evaluate(() => window.__manualAlignSmoke());
  assert.equal(zoomed.viewScale, 2, 'visual zoom control updates view scale');
  await page.click('#reset-view-button');
  const reset = await page.evaluate(() => window.__manualAlignSmoke());
  assert.equal(reset.viewScale, 1, 'reset view restores visual zoom');
  assert.equal(errors.length, 0, errors.join('\n'));
  await browser.close();
  console.log('manual outline align smoke test passed');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
