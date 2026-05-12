// JS harness — runs the actual compare.html algorithms (resample, computeDeltaT)
// against real session parquets via Playwright, so we test what the page runs.
//
// Compares: lap N vs lap N+1 in the latest two sessions, and reports
// computed Delta-t total vs actual lap-time delta.

const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');
const { startServer } = require('./lib/test-server');

const REPO = path.resolve(__dirname, '..');
const WEB_DIR = path.join(REPO, 'web');

const TARGETS = [
  'sessions/Kyalami-mclaren_720s_gt3-15-2020.07.07-02.19.28.parquet',
  'sessions/session_20260512T140000Z_spa-francorchamps_lmu.parquet',
];

(async () => {
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  page.on('console', m => console.log('[console]', m.type(), m.text()));

  await page.goto(url);

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

    // Pick two racing laps from the last segment
    const lastSeg = segs[segs.length - 1];
    if (!lastSeg) {
      console.log('No segments found, skipping');
      continue;
    }

    const laps = await page.evaluate((key, segIdx) => {
      const data = window.__resamplerDebug(key, segIdx);
      // Return unique lap numbers
      const lapSet = new Set(data.lapNumber);
      return [...lapSet].sort((a, b) => a - b);
    }, info.key, lastSeg.segIdx);

    console.log('Lap numbers in segment:', laps.join(', '));

    if (laps.length < 2) {
      console.log('Not enough laps for Δt comparison');
      continue;
    }

    // Compare lap N vs lap N+1
    const lapA = laps[laps.length - 2];
    const lapB = laps[laps.length - 1];

    const dtResult = await page.evaluate((key, segIdx, lapA, lapB) => {
      const data = window.__resamplerDebug(key, segIdx);
      // Find indices for these laps
      const idxA = data.lapNumber.indexOf(lapA);
      const idxB = data.lapNumber.indexOf(lapB);
      if (idxA === -1 || idxB === -1) return null;

      // Use the lap time from the data
      const lapTimeA = data.lapTime[idxA];
      const lapTimeB = data.lapTime[idxB];

      // Compute Δt using the page's algorithm
      const dtData = window.__dtDebug(data, data);
      // dtData is { dist, dtMs, lapTimeSession, lapTimeRef }
      // Find the end-of-lap Δt for lapB
      const endIdx = data.lapNumber.lastIndexOf(lapB);
      const endDt = dtData.dtMs[endIdx];

      return {
        lapTimeA,
        lapTimeB,
        actualDelta: (lapTimeB - lapTimeA) * 1000,
        computedEndDt: endDt
      };
    }, info.key, lastSeg.segIdx, lapA, lapB);

    if (dtResult) {
      console.log(`\nΔt comparison: lap ${lapA} vs lap ${lapB}`);
      console.log(`  Lap time A: ${dtResult.lapTimeA.toFixed(3)} s`);
      console.log(`  Lap time B: ${dtResult.lapTimeB.toFixed(3)} s`);
      console.log(`  Actual Δt: ${(dtResult.actualDelta).toFixed(0)} ms`);
      console.log(`  Computed Δt (end): ${dtResult.computedEndDt?.toFixed(0) ?? 'N/A'} ms`);
      
      if (dtResult.computedEndDt !== null && dtResult.computedEndDt !== undefined) {
        const error = Math.abs(dtResult.computedEndDt - dtResult.actualDelta);
        const pct = (error / Math.abs(dtResult.actualDelta) * 100).toFixed(1);
        console.log(`  Error: ${error.toFixed(0)} ms (${pct}%)`);
      }
    }
  }

  await page.close();
  await browser.close();
  server.close();
  
  console.log('\nDone.');
})().catch(e => { console.error(e); process.exit(1); });
