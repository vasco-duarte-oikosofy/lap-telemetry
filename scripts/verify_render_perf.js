// Time the full load + compare render path on the latest sessions.
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const REPO = path.resolve(__dirname, '..');
const HTML = path.resolve(REPO, 'web', 'compare.html');
const FILE = 'sessions/session_20260510T132500Z_circuit-de-barcelona_lmu.parquet';

(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext()).newPage();
  page.on('pageerror', e => console.log('[pageerror]', e.message));
  await page.goto('file:///' + HTML.replace(/\\/g, '/'));

  const buf = fs.readFileSync(path.resolve(REPO, FILE));
  const fileName = path.basename(FILE);

  console.log('File:', fileName, '(' + (buf.length / 1024).toFixed(0) + ' KB)');

  // ── Phase 1: parquet load ────────────────────────────────────────────
  const t0 = Date.now();
  await page.evaluate(async ({ name, b64 }) => {
    const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    const file = new File([bin], name, { type: 'application/octet-stream' });
    const dt = new DataTransfer();
    dt.items.add(file);
    const input = document.getElementById('file-input');
    input.files = dt.files;
    input.dispatchEvent(new Event('change'));
  }, { name: fileName, b64: buf.toString('base64') });
  await page.waitForFunction(name => window.__getSessionKeys().some(k => k.startsWith(name + '::')), fileName, { timeout: 30000 });
  console.log('Parquet load + parse:', Date.now() - t0, 'ms');

  // ── Phase 2: pick two laps ───────────────────────────────────────────
  const segs = await page.evaluate((name) => {
    const key = window.__getSessionKeys().find(k => k.startsWith(name + '::'));
    const picker = document.getElementById('session-picker');
    return [...picker.querySelectorAll('option')].filter(o => o.value.startsWith(key + '::')).map(o => o.value);
  }, fileName);
  const sVal = segs[3], rVal = segs[4]; // pick two race laps

  // Set values and trigger change → triggers renderAll
  const t1 = Date.now();
  await page.evaluate(({ s, r }) => {
    const sp = document.getElementById('session-picker');
    const rp = document.getElementById('ref-picker');
    sp.value = s; rp.value = r;
    sp.dispatchEvent(new Event('change'));
    // change handler auto-runs renderAll if both selected
  }, { s: sVal, r: rVal });
  // Wait for panels to render
  await page.waitForFunction(() => document.querySelectorAll('#panels .panel-svg').length >= 7, { timeout: 30000 });
  console.log('renderAll (8 panels + circuit map + Δt):', Date.now() - t1, 'ms');

  // ── Phase 3: same render but with cluster-avg disabled (patch in-page) ─
  const t2 = Date.now();
  await page.evaluate(() => {
    // Reach into the module scope: not directly possible. Instead, override
    // by patching window.performance comparison: reload required.
  });
  await browser.close();
  console.log('\nDone.');
})().catch(e => { console.error(e); process.exit(1); });
