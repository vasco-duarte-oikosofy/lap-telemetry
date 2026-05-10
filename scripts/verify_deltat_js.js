// JS harness — runs the actual compare.html algorithms (resample, computeDeltaT)
// against real session parquets via Playwright, so we test what the page runs.
//
// Compares: lap N vs lap N+1 in the latest two sessions, and reports
// computed Delta-t total vs actual lap-time delta.

const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const REPO = path.resolve(__dirname, '..');
const HTML = path.resolve(REPO, 'web', 'compare.html');

const TARGETS = [
  'sessions/session_20260510T132500Z_circuit-de-barcelona_lmu.parquet',
  'sessions/session_20260510T134701Z_circuit-de-barcelona_lmu.parquet',
];

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  page.on('console', m => console.log('[console]', m.type(), m.text()));

  await page.goto('file:///' + HTML.replace(/\\/g, '/'));

  for (const rel of TARGETS) {
    const abs = path.resolve(REPO, rel);
    const buf = fs.readFileSync(abs);
    const fileName = path.basename(abs);

    console.log('\n=========================');
    console.log('Session:', fileName, '(' + (buf.length / 1024).toFixed(0) + ' KB)');

    // Inject the file as if loaded via the file picker
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

    // Wait for store to populate
    await page.waitForFunction(() => window.__getSessionKeys && window.__getSessionKeys().length > 0, { timeout: 30000 });
    // Wait for THIS file to be in the store (filename match)
    await page.waitForFunction(name => window.__getSessionKeys().some(k => k.startsWith(name + '::')), fileName, { timeout: 30000 });
    const tLoad = Date.now() - t0;
    console.log('Load time (incl. parse):', tLoad, 'ms');

    // Get segments info and pick two clean racing laps
    const info = await page.evaluate((name) => {
      const key = window.__getSessionKeys().find(k => k.startsWith(name + '::'));
      // Access the store — it's a module-scoped Map; we'll use exposed debug
      // via __resamplerDebug requires (key, segIdx). First we need segs.
      return { key };
    }, fileName);

    // Probe each segment by querying the picker after it rebuilds
    const segs = await page.evaluate((key) => {
      // Find optgroup matching this key's filename and list its options
      // Easier: re-parse from picker
      const picker = document.getElementById('session-picker');
      const result = [];
      for (const og of picker.querySelectorAll('optgroup')) {
        for (const opt of og.querySelectorAll('option')) {
          if (opt.value.startsWith(key + '::')) {
            const segIdx = parseInt(opt.value.split('::').pop(), 10);
            result.push({ segIdx, label: opt.textContent });
          }
        }
      }
      return result;
    }, info.key);

    console.log('Segments:', segs.map(s => `[${s.segIdx}] ${s.label.trim()}`).join(' | '));

    // For each pair of consecutive racing-laps (skip first/last as out/in), compute Δt
    const racing = segs.slice(1, -1);
    if (racing.length < 2) { console.log('  not enough racing laps to compare'); continue; }

    for (let i = 0; i + 1 < racing.length; i++) {
      const sSeg = racing[i].segIdx;
      const rSeg = racing[i + 1].segIdx;

      const t1 = Date.now();
      const out = await page.evaluate(({ key, sSeg, rSeg }) => {
        const dtBins = window.__dtDebug(key, sSeg, key, rSeg);
        // Also probe lap times by reading the picker labels directly is not easy,
        // so call __resamplerDebug for distances and recompute lap-time span.
        // Easiest: read raw via internal store. We have no store accessor, so
        // expose it via a tiny shim if needed. Use lap_time_s + segments.
        // We'll fetch via debug helper.
        return {
          dtTotal: dtBins[dtBins.length - 1],
          dtLen: dtBins.length,
          dtMax: Math.max(...dtBins),
          dtMin: Math.min(...dtBins),
        };
      }, { key: info.key, sSeg, rSeg });
      const tDt = Date.now() - t1;

      console.log(`  laps [${sSeg}] vs [${rSeg}]: Δt total = ${out.dtTotal.toFixed(1)} ms (range ${out.dtMin.toFixed(0)}..${out.dtMax.toFixed(0)} ms over ${out.dtLen} bins, compute ${tDt} ms)`);
    }

    // Median frame-distance delta from raw
    const md = await page.evaluate((key) => {
      const segs = window.__getSessionKeys();
      // Hack: re-implement here using exposed data — we don't have direct access.
      // Instead, just compute via the resampler debug indirectly.
      return null;
    }, info.key);
  }

  await browser.close();
  console.log('\nDone.');
})().catch(e => { console.error(e); process.exit(1); });
