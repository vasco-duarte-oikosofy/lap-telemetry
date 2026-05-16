/**
 * F16 Auto-Zoom — Feature flag and wiring test suite.
 *
 * Run: node scripts/test_f16_auto_zoom.js
 */
// @parallel true

'use strict';

const { chromium } = require('playwright');
const { startServer } = require('./lib/test-server');
const path = require('path');
const fs = require('fs');

const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'product', 'web');
const SESSIONS_DIR = path.join(ROOT, 'dev', 'sessions');
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', 'f16-auto-zoom-test-report');
const SHOTS_DIR = path.join(REPORT_DIR, 'screenshots');
fs.mkdirSync(SHOTS_DIR, { recursive: true });

const SESSION_FILE = path.join(SESSIONS_DIR, 'session_20260510T074144Z_circuit-de-barcelona_lmu.parquet');

let passCount = 0;
let failCount = 0;
const results = [];

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  results.push({ status, name, detail: String(detail) });
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

async function runTests() {
  console.log('═══ F16 Auto-Zoom — Feature Flag & Wiring Test Suite ═══\n');
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(url);

    // Load a session so the app is fully initialized
    const uploadInput = await page.$('#file-input');
    await uploadInput.setInputFiles(SESSION_FILE);
    await page.waitForFunction(() => {
      const keys = window.__getSessionKeys?.();
      return keys && keys.length > 0;
    }, { timeout: 10000 });

    // ── Assertion 1: mapAutoZoom flag exposed and defaults to false ────────
    console.log('\n════ SCENARIO 1: flag defaults to false ════');
    const defaultVal = await page.evaluate(() => window.__features.mapAutoZoom);
    assert(defaultVal === false, 'mapAutoZoom defaults to false', String(defaultVal));

    // ── Assertion 2: mapAutoZoom appears in feature flag dropdown ─────────
    console.log('\n════ SCENARIO 2: flag appears in dropdown ════');
    const optionValues = await page.$$eval('#feature-flag-menu option', opts =>
      opts.map(o => o.value)
    );
    assert(optionValues.includes('mapAutoZoom'), 'mapAutoZoom appears in feature-flag dropdown', optionValues.join(', '));

    // ── Assertion 3: enabling mapAutoZoom via __setFeatureFlag works ───────
    console.log('\n════ SCENARIO 3: enabling flag via __setFeatureFlag ════');
    await page.evaluate(() => window.__setFeatureFlag('mapAutoZoom', true));
    const enabledVal = await page.evaluate(() => window.__features.mapAutoZoom);
    assert(enabledVal === true, 'mapAutoZoom can be enabled via __setFeatureFlag', String(enabledVal));

    // ── Assertion 4: disabling mapAutoZoom flips it back to false ─────────
    console.log('\n════ SCENARIO 4: disabling flag flips back to false ════');
    await page.evaluate(() => window.__setFeatureFlag('mapAutoZoom', false));
    const disabledVal = await page.evaluate(() => window.__features.mapAutoZoom);
    assert(disabledVal === false, 'mapAutoZoom can be disabled via __setFeatureFlag', String(disabledVal));

    // ── Assertion 5: toggling via dropdown UI works ────────────────────────
    console.log('\n════ SCENARIO 5: toggling via dropdown UI ════');
    // Show the feature-flag menu (hidden by default)
    await page.evaluate(() => window.__setFeatureFlagMenuEnabled(true));
    await page.waitForFunction(() => {
      const menu = document.getElementById('feature-flag-menu');
      return menu && getComputedStyle(menu).display !== 'none';
    });
    // Select mapAutoZoom from dropdown (toggles on) — force needed because
    // Playwright's visibility check may not see the select inside the map panel
    await page.selectOption('#feature-flag-menu', 'mapAutoZoom', { force: true });
    const toggledOn = await page.evaluate(() => window.__features.mapAutoZoom);
    assert(toggledOn === true, 'selecting mapAutoZoom in dropdown toggles it on', String(toggledOn));

    // Select again (toggles off)
    await page.selectOption('#feature-flag-menu', 'mapAutoZoom', { force: true });
    const toggledOff = await page.evaluate(() => window.__features.mapAutoZoom);
    assert(toggledOff === false, 'selecting mapAutoZoom again toggles it off', String(toggledOff));

    // ── Assertion 6: mapAutoZoom depends on mapLinkedHighlight ────────────
    console.log('\n════ SCENARIO 6: mapAutoZoom placed after mapLinkedHighlight ════');
    const flagKeys = await page.evaluate(() => Object.keys(window.__features));
    const mapLHIdx = flagKeys.indexOf('mapLinkedHighlight');
    const mapAZIdx = flagKeys.indexOf('mapAutoZoom');
    assert(mapAZIdx > mapLHIdx, 'mapAutoZoom appears after mapLinkedHighlight in features object',
      `mapLinkedHighlight[${mapLHIdx}], mapAutoZoom[${mapAZIdx}]`);

    // Screenshot artifact
    const png = await page.screenshot({ path: path.join(SHOTS_DIR, 'f16_flag_wiring.png') });
    assert(png.length > 0, 'screenshot written', `${png.length} bytes`);

  } finally {
    await browser.close();
    server.close();
  }

  // ── Write report ─────────────────────────────────────────────────────────
  const reportLines = [
    '# F16 Auto-Zoom — Feature Flag & Wiring Test Report',
    '',
    `Passed: ${passCount}`,
    `Failed: ${failCount}`,
    '',
    '| Status | Assertion | Detail |',
    '|--------|-----------|--------|',
    ...results.map(r => `| ${r.status} | ${r.name} | ${r.detail} |`),
  ];
  fs.writeFileSync(path.join(REPORT_DIR, 'REPORT.md'), reportLines.join('\n'));

  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount > 0) throw new Error(`${failCount} assertions failed`);
}

runTests().catch(err => {
  console.error(err);
  process.exit(1);
});