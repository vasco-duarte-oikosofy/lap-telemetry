/**
 * Feature flag dropdown test suite.
 *
 * Run: node scripts/test_feature_flag_dropdown.js
 */
// @parallel true

'use strict';

const { chromium } = require('playwright');
const { startServer } = require('./lib/test-server');
const path = require('path');

const WEB_DIR = path.join(__dirname, '..', '..', 'product', 'web');
const KNOWN_FLAGS = ['mapWalkingSkeleton', 'mapHeatmapSingleLap', 'mapSAlignment', 'mapDualRibbon', 'mapZoomPan', 'mapLegend', 'mapHover', 'mapLinkedHighlight'];
let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

async function runTests() {
  console.log('═══ Feature Flag Dropdown Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${port}`);

    const exposedFlags = await page.evaluate(() => Object.keys(window.__features || {}));
    assert(KNOWN_FLAGS.every(flag => exposedFlags.includes(flag)), 'known feature flags exposed on window.__features', exposedFlags.join(', '));

    const optionValues = await page.$$eval('#feature-flag-menu option', options => options.map(o => o.value));
    assert(KNOWN_FLAGS.every(flag => optionValues.includes(flag)), 'feature flag dropdown lists known flags', optionValues.join(', '));

    await page.evaluate(() => {
      document.getElementById('circuit-map-panel').style.display = 'block';
      window.__setFeatureFlag('mapHeatmapSingleLap', false);
    });
    await page.selectOption('#feature-flag-menu', 'mapHeatmapSingleLap');
    const enabled = await page.evaluate(() => window.__features.mapHeatmapSingleLap);
    assert(enabled === true, 'selecting a flag option toggles it on', String(enabled));

    const resetToPlaceholder = await page.$eval('#feature-flag-menu', el => el.value);
    assert(resetToPlaceholder === '', 'dropdown resets after toggle so the same flag can be clicked again', resetToPlaceholder);

    await page.selectOption('#feature-flag-menu', 'mapHeatmapSingleLap');
    const disabled = await page.evaluate(() => window.__features.mapHeatmapSingleLap);
    assert(disabled === false, 'selecting the same flag again toggles it off', String(disabled));

    await page.evaluate(() => window.__setFeatureFlagMenuEnabled(false));
    const hidden = await page.$eval('#feature-flag-menu', el => getComputedStyle(el).display === 'none');
    assert(hidden, 'feature flag dropdown can be hidden by console config');

    await page.evaluate(() => window.__setFeatureFlagMenuEnabled(true));
    const visible = await page.$eval('#feature-flag-menu', el => getComputedStyle(el).display !== 'none');
    assert(visible, 'feature flag dropdown can be shown by console config');
  } finally {
    await browser.close();
    server.close();
  }

  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

runTests().catch(err => {
  console.error(err);
  process.exit(1);
});
