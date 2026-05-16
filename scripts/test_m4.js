/**
 * M4 AFK test suite — Playwright headless test for web/compare.html.
 *
 * Run: node scripts/test_m4.js
 *
 * Produces m4-test-report/ with:
 *   screenshots/  — PNG at each state
 *   console.log   — browser console messages
 *   browser_resampled_ref.json   — resampler output from browser (reference lap)
 *   browser_resampled_seg3.json  — resampler output for segment index 3 (lap 4)
 *   REPORT.md     — summary of what passed / failed
 */

'use strict';

const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// ─── Paths ────────────────────────────────────────────────────────────────────
const ROOT = path.resolve(__dirname, '..');
const HTML_FILE = path.join(ROOT, 'web', 'compare.html');
const SESSIONS_DIR = path.join(ROOT, 'sessions');
const REPORT_DIR = path.join(ROOT, 'var', 'test-output', 'm4-test-report');
const SCREENSHOTS_DIR = path.join(REPORT_DIR, 'screenshots');

const SESSION_CLEAN = path.join(SESSIONS_DIR, 'session_20260510T093245Z_circuit-de-barcelona_lmu.parquet');
const SESSION_RESTART = path.join(SESSIONS_DIR, 'session_20260510T091432Z_circuit-de-barcelona_lmu.parquet');
const REF_LAP = path.join(SESSIONS_DIR, 'reference_lap_circuit-de-barcelona_lap5.parquet');

// ─── Setup ───────────────────────────────────────────────────────────────────
fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

// ─── Local HTTP server (serves compare.html + static files) ──────────────────
function startServer() {
  const server = http.createServer((req, res) => {
    // Only serve compare.html
    const filePath = HTML_FILE;
    try {
      const content = fs.readFileSync(filePath);
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.end(content);
    } catch (e) {
      res.writeHead(404);
      res.end('Not found');
    }
  });
  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      resolve({ server, port });
    });
  });
}

// ─── Test runner ─────────────────────────────────────────────────────────────
const consoleLogs = [];
const results = [];
let failCount = 0;

function assert(condition, name, detail = '') {
  const status = condition ? 'PASS' : 'FAIL';
  if (!condition) failCount++;
  results.push({ status, name, detail });
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
  return condition;
}

async function screenshot(page, name) {
  const dest = path.join(SCREENSHOTS_DIR, `${name}.png`);
  await page.screenshot({ path: dest, fullPage: false });
  console.log(`  📸 ${name}.png`);
}

async function waitForStatus(page, selector, contains, timeout = 20000) {
  await page.waitForFunction(
    ({ sel, text }) => {
      const el = document.querySelector(sel);
      return el && el.textContent.includes(text);
    },
    { sel: selector, text: contains },
    { timeout }
  );
}

async function runFixture(page, { sessionPath, refPath, expectedLaps, fixtureName, segIdxToPlot }) {
  console.log(`\n── Fixture: ${fixtureName} ──`);

  // Load session
  console.log('  Loading session file…');
  await page.setInputFiles('#session-input', sessionPath);
  try {
    await waitForStatus(page, '#session-status', 'rows', 30000);
    const statusText = await page.$eval('#session-status', el => el.textContent);
    assert(statusText.includes('rows'), `${fixtureName}: session status shows rows`, statusText);
    await screenshot(page, `${fixtureName}_01_session_loaded`);
  } catch (e) {
    assert(false, `${fixtureName}: session loaded within 30s`, e.message);
    await screenshot(page, `${fixtureName}_01_session_error`);
    return;
  }

  // Count picker options
  const optionCount = await page.$eval('#lap-picker', sel => sel.options.length);
  assert(
    optionCount === expectedLaps,
    `${fixtureName}: picker has ${expectedLaps} options`,
    `got ${optionCount}`
  );

  // Load reference
  console.log('  Loading reference file…');
  await page.setInputFiles('#ref-input', refPath);
  try {
    await waitForStatus(page, '#ref-status', 'rows', 30000);
    const refStatusText = await page.$eval('#ref-status', el => el.textContent);
    assert(refStatusText.includes('rows'), `${fixtureName}: ref status shows rows`, refStatusText);
    await screenshot(page, `${fixtureName}_02_ref_loaded`);
  } catch (e) {
    assert(false, `${fixtureName}: reference loaded within 30s`, e.message);
    return;
  }

  // Pick a lap and compare
  console.log(`  Selecting segment index ${segIdxToPlot}…`);
  await page.selectOption('#lap-picker', String(segIdxToPlot));
  await page.click('#compare-btn');

  // Wait for polylines
  try {
    await page.waitForSelector('polyline.session-line', { timeout: 10000 });
    await screenshot(page, `${fixtureName}_03_plot_rendered`);

    const polylineCount = await page.$$eval('polyline', els => els.length);
    assert(polylineCount >= 2, `${fixtureName}: SVG has ≥2 polyline elements`, `got ${polylineCount}`);

    // Verify plot is visible
    const plotVisible = await page.$eval('#plot', el => el.style.display !== 'none');
    assert(plotVisible, `${fixtureName}: plot SVG is visible`);
  } catch (e) {
    assert(false, `${fixtureName}: plot rendered with polylines`, e.message);
    await screenshot(page, `${fixtureName}_03_plot_error`);
  }

  return optionCount;
}

async function main() {
  const { server, port } = await startServer();
  const url = `http://127.0.0.1:${port}`;

  console.log(`\n═══ M4 AFK Test Suite ═══`);
  console.log(`Serving: ${HTML_FILE}`);
  console.log(`URL: ${url}`);
  console.log(`Report dir: ${REPORT_DIR}\n`);

  const browser = await chromium.launch({ headless: true });

  try {
    // ── FIXTURE 1: Clean 6-lap session ─────────────────────────────────────
    console.log('\n════ FIXTURE 1: Clean 6-lap session ════');
    const ctx1 = await browser.newContext();
    const page1 = await ctx1.newPage();

    page1.on('console', msg => {
      const entry = `[${msg.type()}] ${msg.text()}`;
      consoleLogs.push(entry);
      if (msg.type() === 'error' || msg.type() === 'warning' || msg.text().startsWith('DBG')) {
        console.warn(`  ⚠ CONSOLE ${msg.type().toUpperCase()}: ${msg.text()}`);
      }
    });
    page1.on('pageerror', err => {
      const entry = `[pageerror] ${err.message}`;
      consoleLogs.push(entry);
      console.error(`  ✖ PAGE ERROR: ${err.message}`);
    });

    await page1.goto(url);
    await screenshot(page1, 'clean_00_initial');

    // Assert picker is disabled initially
    const pickerDisabled = await page1.$eval('#lap-picker', el => el.disabled);
    assert(pickerDisabled, 'Initial: picker is disabled');

    await runFixture(page1, {
      sessionPath: SESSION_CLEAN,
      refPath: REF_LAP,
      expectedLaps: 6,
      fixtureName: 'clean',
      segIdxToPlot: 3,  // Lap 4 (1:37.842)
    });

    // ── Resampler cross-check ────────────────────────────────────────────────
    console.log('\n  Resampler cross-check…');
    try {
      // Browser resampler: reference lap (all rows in ref file)
      const browserRefBins = await page1.evaluate(() => window.__refResamplerDebug());
      const browserRefPath = path.join(REPORT_DIR, 'browser_resampled_ref.json');
      fs.writeFileSync(browserRefPath, JSON.stringify(browserRefBins));

      // Browser resampler: session segment 3 (lap 4)
      const browserSegBins = await page1.evaluate(() => window.__resamplerDebug(3));
      const browserSegPath = path.join(REPORT_DIR, 'browser_resampled_seg3.json');
      fs.writeFileSync(browserSegPath, JSON.stringify(browserSegBins));

      // Python resampler: reference lap
      const pythonRefPath = path.join(REPORT_DIR, 'python_resampled_ref.json');
      execSync(`python "${path.join(ROOT, 'scripts', 'check_resampler.py')}" "${REF_LAP}" --out "${pythonRefPath}"`, { cwd: ROOT });
      const pythonRefBins = JSON.parse(fs.readFileSync(pythonRefPath, 'utf8'));

      // Compare
      const minLen = Math.min(browserRefBins.length, pythonRefBins.length);
      let maxDiff = 0, sumDiff = 0;
      for (let i = 0; i < minLen; i++) {
        const diff = Math.abs(browserRefBins[i] - pythonRefBins[i]);
        if (diff > maxDiff) maxDiff = diff;
        sumDiff += diff;
      }
      const meanDiff = sumDiff / minLen;
      const lenMatch = Math.abs(browserRefBins.length - pythonRefBins.length) <= 2;

      console.log(`  Resampler diff: max=${maxDiff.toFixed(4)} km/h, mean=${meanDiff.toFixed(4)} km/h`);
      console.log(`  Bin counts: browser=${browserRefBins.length}, python=${pythonRefBins.length}`);

      assert(maxDiff < 0.1, 'Resampler: max|browser - python| < 0.1 km/h', `got ${maxDiff.toFixed(4)}`);
      assert(lenMatch, 'Resampler: bin count matches', `browser=${browserRefBins.length} python=${pythonRefBins.length}`);

      // Write diff summary
      const diffSummary = `Resampler diff (reference lap)\n` +
        `Browser bins: ${browserRefBins.length}\n` +
        `Python bins:  ${pythonRefBins.length}\n` +
        `Max |diff|:   ${maxDiff.toFixed(6)} km/h\n` +
        `Mean |diff|:  ${meanDiff.toFixed(6)} km/h\n` +
        `Threshold:    0.1 km/h\n` +
        `Result:       ${maxDiff < 0.1 ? 'PASS' : 'FAIL'}\n`;
      fs.writeFileSync(path.join(REPORT_DIR, 'resampler_diff.txt'), diffSummary);
      console.log('  Wrote resampler_diff.txt');
    } catch (e) {
      assert(false, 'Resampler cross-check', e.message);
      console.error('  Resampler error:', e.message);
    }

    await ctx1.close();

    // ── FIXTURE 2: Restart session (7 laps) ─────────────────────────────────
    console.log('\n════ FIXTURE 2: Restart-session (7 segments) ════');
    const ctx2 = await browser.newContext();
    const page2 = await ctx2.newPage();

    page2.on('console', msg => {
      consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
      if (msg.type() === 'error' || msg.type() === 'warning') {
        console.warn(`  ⚠ CONSOLE ${msg.type().toUpperCase()}: ${msg.text()}`);
      }
    });
    page2.on('pageerror', err => {
      consoleLogs.push(`[pageerror] ${err.message}`);
      console.error(`  ✖ PAGE ERROR: ${err.message}`);
    });

    await page2.goto(url);

    await runFixture(page2, {
      sessionPath: SESSION_RESTART,
      refPath: REF_LAP,
      expectedLaps: 7,
      fixtureName: 'restart',
      segIdxToPlot: 2,  // Segment 3 (lap 5 in original numbering, 1:44.482)
    });

    // Check lap numbers in picker are in chronological order
    try {
      const pickerLabels = await page2.$$eval('#lap-picker option', opts => opts.map(o => o.textContent));
      console.log('  Picker options:');
      pickerLabels.forEach((l, i) => console.log(`    [${i}] ${l.trim()}`));
      // Restart session has segments: 3,4,5,6,7,0,1 — check first and last
      const firstLapNum = pickerLabels[0].match(/lap#\s*(\d+)/)?.[1];
      const lastLapNum  = pickerLabels[pickerLabels.length - 1].match(/lap#\s*(\d+)/)?.[1];
      assert(firstLapNum === '3', 'Restart: first segment is lap# 3', `got ${firstLapNum}`);
      assert(lastLapNum === '1', 'Restart: last segment is lap# 1 (post-restart)', `got ${lastLapNum}`);
    } catch (e) {
      assert(false, 'Restart: picker chronological order check', e.message);
    }

    await ctx2.close();

  } finally {
    await browser.close();
    server.close();
  }

  // ── Console log check ────────────────────────────────────────────────────
  const consoleLogPath = path.join(REPORT_DIR, 'console.log');
  fs.writeFileSync(consoleLogPath, consoleLogs.join('\n'), 'utf8');

  const errorLines = consoleLogs.filter(l => l.startsWith('[error]') || l.startsWith('[pageerror]'));
  const warnLines  = consoleLogs.filter(l => l.startsWith('[warning]'));
  assert(errorLines.length === 0, 'Console: no error entries', `${errorLines.length} errors`);
  if (warnLines.length > 0) {
    console.log(`  ℹ ${warnLines.length} console warnings (not a failure):`);
    warnLines.forEach(w => console.log(`    ${w}`));
  }

  // ── Write REPORT.md ──────────────────────────────────────────────────────
  const now = new Date().toISOString();
  const passCount = results.filter(r => r.status === 'PASS').length;
  const totalCount = results.length;

  const reportLines = [
    `# M4 Test Report`,
    ``,
    `Generated: ${now}`,
    `Result: **${failCount === 0 ? 'ALL PASS' : failCount + ' FAILURES'}** (${passCount}/${totalCount})`,
    ``,
    `## Assertions`,
    ``,
    `| Status | Test | Detail |`,
    `|--------|------|--------|`,
    ...results.map(r => `| ${r.status} | ${r.name} | ${r.detail || ''} |`),
    ``,
    `## Files`,
    ``,
    `- \`screenshots/\` — browser state at each step`,
    `- \`console.log\` — full browser console output (${consoleLogs.length} lines)`,
    `- \`resampler_diff.txt\` — max/mean absolute diff between browser and Python resampler`,
    `- \`browser_resampled_ref.json\` — browser resampled reference lap (${'' } bins)`,
    `- \`python_resampled_ref.json\` — Python resampled reference lap`,
    `- \`browser_resampled_seg3.json\` — browser resampled session segment 3`,
    ``,
    `## Console warnings (${warnLines.length})`,
    warnLines.length ? warnLines.map(w => `- \`${w}\``).join('\n') : '(none)',
    ``,
    `## Console errors (${errorLines.length})`,
    errorLines.length ? errorLines.map(e => `- \`${e}\``).join('\n') : '(none)',
  ];

  fs.writeFileSync(path.join(REPORT_DIR, 'REPORT.md'), reportLines.join('\n'), 'utf8');

  // ── Summary ──────────────────────────────────────────────────────────────
  console.log('\n═══════════════════════════════════');
  console.log(`  ${passCount}/${totalCount} assertions passed`);
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
