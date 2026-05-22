// @parallel true
// Regression test: loading a parquet with very long uniform RLE runs must not
// throw "Maximum call stack size exceeded".
//
// Root cause: hyparquet expands RLE runs via spread (push(...largeArray)) which
// overflows the JS call stack for single-run columns like abs_active=false for
// 330k frames, or terrain_name_fl='ROAD' for the whole session.
//
// Fix: abs_active, tc_active, and terrain_name_* are loaded in isolated
// readColumns calls so a per-column overflow cannot kill the whole file load.
//
// Run: node dev/scripts/test_uniform_rle_load.js

'use strict';

const { chromium } = require('playwright');
const path = require('path');
const { startServer } = require('./lib/test-server');

const ROOT     = path.resolve(__dirname, '..', '..');
const WEB_DIR  = path.join(ROOT, 'product', 'web');
const FIXTURE  = path.join(ROOT, 'dev', 'scripts', 'parquet-fixture-uniform-rle.parquet');

let failCount = 0;
const results = [];

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failCount++;
  results.push({ status, name, detail });
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
  return cond;
}

async function waitForStatus(page, selector, text, timeout = 15000) {
  await page.waitForFunction(
    ({ sel, txt }) => {
      const el = document.querySelector(sel);
      return el && el.textContent.includes(txt);
    },
    { sel: selector, txt: text },
    { timeout }
  );
}

(async () => {
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch({ headless: true });

  try {
    const page = await browser.newPage();
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    page.on('pageerror', err => consoleErrors.push(err.message));

    await page.goto(url);

    // Load the fixture — a parquet with abs_active=false and terrain_name='ROAD'
    // for every row (uniform RLE runs across the whole file).
    await page.setInputFiles('#file-input', FIXTURE);

    // The file must load successfully (badge shows rows, not an error).
    await waitForStatus(page, '#session-list .badge.ok', 'rows', 15000);

    const badge = await page.$eval('#session-list .badge.ok', el => el.textContent);
    assert(badge.includes('rows'), 'T1: uniform-RLE parquet loads without stack overflow', badge);
    assert(!badge.includes('error'), 'T2: no error badge on load', badge);

    // No "Failed to load" error toast should be visible.
    const errorEl = await page.$('#error-display');
    const errorVisible = errorEl ? await errorEl.isVisible() : false;
    assert(!errorVisible, 'T3: no error toast displayed');

    // No Maximum call stack size error in console.
    const stackErr = consoleErrors.find(e => e.includes('Maximum call stack'));
    assert(!stackErr, 'T4: no stack overflow in console', stackErr || '');

    // The load-status should show 1 file loaded.
    const loadStatus = await page.$eval('#load-status', el => el.textContent);
    assert(loadStatus.includes('1'), 'T5: load-status shows 1 file loaded', loadStatus);

  } finally {
    await browser.close();
    server.close();
  }

  const passCount = results.filter(r => r.status === 'PASS').length;
  console.log(`\n${'─'.repeat(60)}`);
  if (failCount > 0) {
    console.log(`  ✖ ${failCount} FAILURES`);
    results.filter(r => r.status === 'FAIL').forEach(r =>
      console.log(`    FAIL: ${r.name}${r.detail ? ' [' + r.detail.slice(0, 80) + ']' : ''}`)
    );
    process.exit(1);
  } else {
    console.log(`  ✔ ${passCount} assertions passed`);
  }
})().catch(err => {
  console.error('Test error:', err);
  process.exit(1);
});
