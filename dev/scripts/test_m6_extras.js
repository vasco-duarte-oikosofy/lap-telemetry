// @parallel true
// Smoke test for the four post-F4 additions:
//   - persistent zoom (localStorage roundtrip)
//   - sidecar metadata (parquet+json multi-load, picker labels include vehicle)
//   - Δt sector-breakdown labels on the dt panel
//   - circuit-map heatmap (track-segments populated when mode != outline)
//
// Uses a fresh F4 session (latest 142624Z) so we know it has good data.

const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');
const { startServer } = require('./lib/test-server');

const REPO = path.resolve(__dirname, '..', '..');
const WEB_DIR = path.join(REPO, 'web');
const PARQUET = 'dev/sessions/session_20260511T151203Z_circuit-de-barcelona_lmu.parquet';
const JSON_SIDECAR = 'dev/sessions/session_20260511T151203Z_circuit-de-barcelona_lmu.json';

let pass = 0, fail = 0;
function assert(cond, msg) {
  if (cond) { pass++; console.log('  [PASS]', msg); }
  else      { fail++; console.log('  [FAIL]', msg); }
}

(async () => {
  const { server, port } = await startServer(WEB_DIR);
  const url = `http://127.0.0.1:${port}`;
  
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  page.on('pageerror', e => { fail++; console.log('  [pageerror]', e.message); });
  page.on('console', m => { if (m.type() === 'error') console.log('  [console err]', m.text()); });

  await page.goto(url);

  // ── Inject parquet + sidecar JSON via the multi-file picker ─────────────
  const pBuf = fs.readFileSync(path.resolve(REPO, PARQUET));
  const jBuf = fs.readFileSync(path.resolve(REPO, JSON_SIDECAR));
  const pName = path.basename(PARQUET);
  const jName = path.basename(JSON_SIDECAR);

  await page.evaluate(async ({ files }) => {
    const dt = new DataTransfer();
    for (const f of files) {
      const bin = Uint8Array.from(atob(f.b64), c => c.charCodeAt(0));
      dt.items.add(new File([bin], f.name, { type: 'application/octet-stream' }));
    }
    const input = document.getElementById('file-input');
    input.files = dt.files;
    input.dispatchEvent(new Event('change'));
  }, { files: [
    { name: pName, b64: pBuf.toString('base64') },
    { name: jName, b64: jBuf.toString('base64') },
  ]});

  await page.waitForFunction(name => window.__getSessionKeys().some(k => k.startsWith(name + '::')), pName, { timeout: 30000 });

  console.log('\n── Sidecar metadata ─────────────────────────────');
  const pickerHtml = await page.evaluate(() => document.getElementById('session-picker').innerHTML);
  assert(pickerHtml.includes('JMW') || pickerHtml.includes('GT3'), 'picker label includes vehicle short-name (JMW/GT3)');
  assert(pickerHtml.includes('296') || pickerHtml.includes('Balanced'), 'picker label includes setup file (296/Balanced)');
  const sessionListBadge = await page.evaluate(() => document.querySelector('.session-entry .badge')?.textContent || '');
  assert(/JMW|#66/.test(sessionListBadge), `session-list badge shows vehicle  →  ${sessionListBadge.slice(0,80)}`);

  // ── Compare two laps so renderAll fires (lap 1 vs 2) ────────────────────
  await page.evaluate(() => {
    const opts = [...document.getElementById('session-picker').querySelectorAll('option')].filter(o => o.value);
    const sp = document.getElementById('session-picker');
    const rp = document.getElementById('ref-picker');
    sp.value = opts[1].value;  // first racing lap
    rp.value = opts[2].value;
    sp.dispatchEvent(new Event('change'));
  });
  await page.waitForFunction(() => document.querySelectorAll('#panels .panel-svg').length >= 7, { timeout: 30000 });

  console.log('\n── Δt sector breakdown ─────────────────────────');
  const dtTexts = await page.evaluate(() => {
    const dtSvg = document.querySelector('[data-panel-id="dt"]');
    return [...dtSvg.querySelectorAll('text')].map(t => t.textContent);
  });
  const sectorLabels = dtTexts.filter(t => /^[+-]?\d+ ms$/.test(t.trim()));
  const endLabel = dtTexts.find(t => /^end [+-]\d+ ms$/.test(t.trim()));
  assert(sectorLabels.length >= 2, `Δt has at least 2 sector readouts (S2,S3)  →  got ${sectorLabels.length}: ${sectorLabels.join(' | ')}`);
  assert(!!endLabel, `Δt has lap-end readout  →  ${endLabel || '(none)'}`);

  console.log('\n── Circuit-map heatmap ────────────────────────');
  // Initially: outline mode, no segments.
  const initialSegCount = await page.evaluate(() => document.querySelectorAll('#track-segments line').length);
  assert(initialSegCount === 0, `outline mode: 0 segments rendered  →  got ${initialSegCount}`);

  for (const mode of ['speed', 'brake', 'throttle']) {
    await page.evaluate(m => {
      const sel = document.getElementById('map-mode');
      sel.value = m;
      sel.dispatchEvent(new Event('change'));
    }, mode);
    const segCount = await page.evaluate(() => document.querySelectorAll('#track-segments line').length);
    const outlineHidden = await page.evaluate(() => document.getElementById('track-outline').style.display === 'none');
    const legendHtml = await page.evaluate(() => document.getElementById('map-legend').innerHTML);
    assert(segCount > 100, `${mode}: heatmap segments rendered (>100)  →  got ${segCount}`);
    assert(outlineHidden, `${mode}: outline polyline hidden`);
    assert(legendHtml.includes('linear-gradient'), `${mode}: legend shows colour ramp`);
  }
  // Back to outline.
  await page.evaluate(() => {
    const sel = document.getElementById('map-mode');
    sel.value = 'outline';
    sel.dispatchEvent(new Event('change'));
  });
  const finalSegCount = await page.evaluate(() => document.querySelectorAll('#track-segments line').length);
  const outlineShown = await page.evaluate(() => document.getElementById('track-outline').style.display !== 'none');
  assert(finalSegCount === 0 && outlineShown, 'switching back to outline restores polyline + clears segments');

  console.log('\n── Persistent zoom ────────────────────────────');
  // Store a zoom state directly via the persistor (we test the round-trip,
  // not the drag interaction itself — that's covered by F1F2 tests).
  await page.evaluate(() => localStorage.setItem('lap-telemetry.zoom.v1', JSON.stringify({ start: 500, end: 1500 })));
  await page.reload();
  await page.waitForFunction(() => !!document.getElementById('file-input'), { timeout: 5000 });

  // Reload + reload the session and compare again.
  await page.evaluate(async ({ files }) => {
    const dt = new DataTransfer();
    for (const f of files) {
      const bin = Uint8Array.from(atob(f.b64), c => c.charCodeAt(0));
      dt.items.add(new File([bin], f.name, { type: 'application/octet-stream' }));
    }
    const input = document.getElementById('file-input');
    input.files = dt.files;
    input.dispatchEvent(new Event('change'));
  }, { files: [
    { name: pName, b64: pBuf.toString('base64') },
    { name: jName, b64: jBuf.toString('base64') },
  ]});
  await page.waitForFunction(name => window.__getSessionKeys().some(k => k.startsWith(name + '::')), pName, { timeout: 30000 });
  await page.evaluate(() => {
    const opts = [...document.getElementById('session-picker').querySelectorAll('option')].filter(o => o.value);
    const sp = document.getElementById('session-picker');
    const rp = document.getElementById('ref-picker');
    sp.value = opts[1].value;
    rp.value = opts[2].value;
    sp.dispatchEvent(new Event('change'));
  });
  await page.waitForFunction(() => document.querySelectorAll('#panels .panel-svg').length >= 7, { timeout: 30000 });

  // Verify zoom-arc is visible (= zoom is active) after reload.
  const zoomArcDisplay = await page.evaluate(() => document.getElementById('zoom-arc').style.display);
  assert(zoomArcDisplay === 'block', `zoom restored from localStorage on reload  →  zoom-arc display = "${zoomArcDisplay}"`);

  // Cleanup so we don't leave persisted state behind.
  await page.evaluate(() => localStorage.removeItem('lap-telemetry.zoom.v1'));

  await page.close();
  await browser.close();
  server.close();

  console.log('\n═══════════════════════════════════');
  console.log(`  ${pass}/${pass + fail} assertions passed`);
  console.log(fail === 0 ? '  ✔ All extras passed' : `  ✘ ${fail} failed`);
  console.log('═══════════════════════════════════');
  process.exit(fail === 0 ? 0 : 1);
})().catch(e => { console.error(e); process.exit(1); });
