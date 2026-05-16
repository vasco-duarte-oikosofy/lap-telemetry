/**
 * M4 AFK test suite — Playwright headless test for web/compare.html.
 *
 * Tests: file loading, picker population, plot rendering, resampler cross-check.
 *
 * Run: node scripts/test_m4.js
 */
// @parallel true

'use strict';

const {
  chromium,
} = require('playwright');
const fs = require('fs');
const path = require('path');
const { startServer } = require('./lib/test-server');

// ─── Paths ────────────────────────────────────────────────────────────────────
const ROOT = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'product', 'web');
const SESSIONS_DIR = path.join(ROOT, 'dev', 'sessions');
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', 'm4-test-report');
const SCREENSHOTS_DIR = path.join(REPORT_DIR, 'screenshots');

const SESSION_CLEAN = path.join(SESSIONS_DIR, 'session_20260511T151203Z_circuit-de-barcelona_lmu.parquet');

// ─── Setup ───────────────────────────────────────────────────────────────────
fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

// ─── Test state ────────────────────────────────────────────────────────────
const consoleLogs = [];
const results = [];
let passCount = 0;
let failCount = 0;

function assert(condition, name, detail = '') {
  const status = condition ? 'PASS' : 'FAIL';
  if (condition) passCount++; else failCount++;
  results.push({ status, name, detail });
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
  return condition;
}

async function screenshot(page, name) {
  const dest = path.join(SCREENSHOTS_DIR, `${name}.png`);
  await page.screenshot({ path: dest, fullPage: false });
  console.log(`  📸 ${name}.png`);
}

async function waitForStatus(page, selector, contains, timeout = 30000) {
  await page.waitForFunction(
    ({ sel, text }) => {
      const el = document.querySelector(sel);
      return el && el.textContent.includes(text);
    },
    { sel: selector, text: contains },
    { timeout }
  );
}

// ─── Main ──────────────────────────────────────────────────────────────────
async function main() {
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;

  console.log(`\n═══ M4 AFK Test Suite ═══`);
  console.log(`URL: ${url}`);
  console.log(`Report dir: ${REPORT_DIR}\n`);

  const browser = await chromium.launch({ headless: true });

  try {
    // ── Fixture 1: Load session, pick laps, compare ──
    console.log('\n── Fixture 1: Load session and compare ──');
    const ctx1 = await browser.newContext();
    const page1 = await ctx1.newPage();

    page1.on('console', msg => {
      const entry = `[${msg.type()}] ${msg.text()}`;
      consoleLogs.push(entry);
      if (msg.type() === 'error' || msg.type() === 'warning') {
        console.warn(`  ⚠ CONSOLE ${msg.type().toUpperCase()}: ${msg.text()}`);
      }
    });
    page1.on('pageerror', err => {
      const entry = `[pageerror] ${err.message}`;
      consoleLogs.push(entry);
      console.error(`  ✖ PAGE ERROR: ${err.message}`);
    });

    await page1.goto(url);
    await screenshot(page1, 'f1_00_initial');

    // Load session file
    await page1.locator('#load-btn').click();
    await page1.setInputFiles('#file-input', [SESSION_CLEAN]);
    await waitForStatus(page1, '#session-list .badge.ok', 'rows', 30000);

    const badge1 = await page1.$eval('#session-list .badge.ok', el => el.textContent);
    assert(badge1.includes('rows'), 'F1: session loaded', badge1);
    await screenshot(page1, 'f1_01_loaded');

    // Check pickers populated (7 segments)
    const spCount = await page1.$eval('#session-picker', s => s.options.length);
    assert(spCount > 0, 'F1: session picker populated', `${spCount} options`);
    const rpCount = await page1.$eval('#ref-picker', s => s.options.length);
    assert(rpCount > 0, 'F1: ref picker populated', `${rpCount} options`);

    // Get store keys and pick laps
    const storeKeys = await page1.evaluate(() => window.__getSessionKeys());
    assert(storeKeys.length === 1, 'F1: store has 1 entry', `got ${storeKeys.length}`);
    const sk = storeKeys[0];

    // Select session segment 2 (lap 3) and ref segment 3 (lap 4)
    const sessionVal = `${sk}::2`;
    const refVal = `${sk}::3`;
    await page1.selectOption('#session-picker', sessionVal);
    await page1.selectOption('#ref-picker', refVal);
    await page1.click('#compare-btn');

    // Wait for plot to render
    try {
      await page1.waitForFunction(() => {
        return document.querySelectorAll('#panels .panel-svg').length >= 1 &&
          document.querySelectorAll('svg[data-panel-id="dt"] polyline').length >= 1;
      }, { timeout: 10000 });
      await screenshot(page1, 'f1_02_compare');

      const panelCount = await page1.$$eval('.panel-wrap', els => els.length);
      assert(panelCount >= 1, 'F1: plot panels rendered', `got ${panelCount}`);

      const dtPolylines = await page1.$$eval('svg[data-panel-id="dt"] polyline', els => els.length);
      assert(dtPolylines >= 1, 'F1: Δt panel has polyline', `got ${dtPolylines}`);
    } catch (e) {
      assert(false, 'F1: plot rendered', e.message);
      await screenshot(page1, 'f1_02_compare_error');
    }

    // ── Resampler cross-check ──
    // Verify that the browser resampler produces consistent output for
    // two different segments of the same session.
    console.log('\n  Resampler cross-check…');
    try {
      // Resample segment 2 (lap 3) and segment 3 (lap 4) from same session
      const seg2Bins = await page1.evaluate(sk => window.__resamplerDebug(sk, 2), sk);
      const seg3Bins = await page1.evaluate(sk => window.__resamplerDebug(sk, 3), sk);

      assert(Array.isArray(seg2Bins) && seg2Bins.length > 0, 'Resampler: segment 2 produces output', `got ${Array.isArray(seg2Bins) ? seg2Bins.length : 'not array'}`);
      assert(Array.isArray(seg3Bins) && seg3Bins.length > 0, 'Resampler: segment 3 produces output', `got ${Array.isArray(seg3Bins) ? seg3Bins.length : 'not array'}`);

      // All values should be finite numbers
      const allFinite = seg2Bins.every(v => Number.isFinite(v)) && seg3Bins.every(v => Number.isFinite(v));
      assert(allFinite, 'Resampler: all values are finite numbers');

      // Different segments should produce different speed profiles
      const meanDiff = seg2Bins.reduce((s, v, i) => s + Math.abs(v - (seg3Bins[i] ?? 0)), 0) / Math.min(seg2Bins.length, seg3Bins.length);
      assert(meanDiff > 0.5, 'Resampler: different segments produce different profiles', `mean diff = ${meanDiff.toFixed(2)}`);

      fs.writeFileSync(path.join(REPORT_DIR, 'browser_resampled_seg2.json'), JSON.stringify(seg2Bins));
      fs.writeFileSync(path.join(REPORT_DIR, 'browser_resampled_seg3.json'), JSON.stringify(seg3Bins));
      console.log(`  Segment 2 bins: ${seg2Bins.length}, segment 3 bins: ${seg3Bins.length}`);
    } catch (e) {
      assert(false, 'Resampler cross-check', e.message);
      console.error('  Resampler error:', e.message);
    }

    await ctx1.close();

    // ── Fixture 2: Restart session (7 laps) ──
    console.log('\n── Fixture 2: Restart session ──');
    const SESSION_RESTART = path.join(SESSIONS_DIR, 'session_20260510T140409Z_circuit-de-barcelona_lmu.parquet');

    const ctx2 = await browser.newContext();
    const page2 = await ctx2.newPage();
    page2.on('console', msg => {
      consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
    });

    await page2.goto(url);

    // Load both session files
    await page2.locator('#load-btn').click();
    await page2.setInputFiles('#file-input', [SESSION_CLEAN, SESSION_RESTART]);
    await waitForStatus(page2, '#session-list .badge.ok', 'rows', 30000);

    const badge2 = await page2.$eval('#session-list .badge.ok', el => el.textContent);
    assert(badge2.includes('rows'), 'F2: sessions loaded', badge2);
    await screenshot(page2, 'f2_01_loaded');

    // Check picker has options from both sessions
    const spCount2 = await page2.$eval('#session-picker', s => s.options.length);
    assert(spCount2 > 0, 'F2: session picker populated', `${spCount2} options`);
    const rpCount2 = await page2.$eval('#ref-picker', s => s.options.length);
    assert(rpCount2 > 0, 'F2: ref picker populated', `${rpCount2} options`);

    await ctx2.close();

  } finally {
    await browser.close();
    server.close();
  }

  // ── Console log check ──
  const consoleLogPath = path.join(REPORT_DIR, 'console.log');
  fs.writeFileSync(consoleLogPath, consoleLogs.join('\n'), 'utf8');

  const errorLines = consoleLogs.filter(l => l.startsWith('[error]') || l.startsWith('[pageerror]'));
  assert(errorLines.length === 0, 'Console: no error entries', `${errorLines.length} errors`);

  // ── Write REPORT.md ──
  const now = new Date().toISOString();
  const reportLines = [
    `# M4 Test Report`,
    ``,
    `Generated: ${now}`,
    `Result: **${failCount === 0 ? 'ALL PASS' : failCount + ' FAILURES'}** (${passCount}/${passCount + failCount})`,
    ``,
    `## Assertions`,
    ``,
    `| Status | Test | Detail |`,
    `|--------|------|--------|`,
    ...results.map(r => `| ${r.status} | ${r.name} | ${r.detail || ''} |`),
  ];
  fs.writeFileSync(path.join(REPORT_DIR, 'REPORT.md'), reportLines.join('\n'), 'utf8');

  // ── Summary ──
  console.log('\n═══════════════════════════════════');
  console.log(`  ${passCount}/${passCount + failCount} assertions passed`);
  if (failCount > 0) {
    console.log(`  ✖ ${failCount} FAILURES — see m4-test-report/REPORT.md`);
    results.filter(r => r.status === 'FAIL').forEach(r =>
      console.log(`    FAIL: ${r.name}${r.detail ? ' [' + r.detail + ']' : ''}`)
    );
  } else {
    console.log('  ✔ All assertions passed');
  }
  console.log(`  Report: ${REPORT_DIR}`);
  console.log('═══════════════════════════════════\n');

  process.exit(failCount > 0 ? 1 : 0);
}

main().catch(e => {
  console.error('Fatal error:', e);
  process.exit(2);
});