/**
 * M5 AFK test suite — Playwright headless test for web/compare.html (M5).
 *
 * Run: node scripts/test_m5.js
 *
 * Produces m5-test-report/ with screenshots, console log, Δt diff, REPORT.md.
 */

'use strict';

const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execSync, spawnSync } = require('child_process');

// ── Paths ─────────────────────────────────────────────────────────────────────
const ROOT         = path.resolve(__dirname, '..');
const HTML_FILE    = path.join(ROOT, 'web', 'compare.html');
const SESSIONS_DIR = path.join(ROOT, 'sessions');
const REPORT_DIR   = path.join(ROOT, 'm5-test-report');
const SHOTS_DIR    = path.join(REPORT_DIR, 'screenshots');

const SESSION_CLEAN   = path.join(SESSIONS_DIR, 'session_20260510T093245Z_circuit-de-barcelona_lmu.parquet');
const SESSION_RESTART = path.join(SESSIONS_DIR, 'session_20260510T091432Z_circuit-de-barcelona_lmu.parquet');

fs.mkdirSync(SHOTS_DIR, { recursive: true });

// ── HTTP server ───────────────────────────────────────────────────────────────
function startServer() {
  const server = http.createServer((req, res) => {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end(fs.readFileSync(HTML_FILE));
  });
  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => {
      resolve({ server, port: server.address().port });
    });
  });
}

// ── Test utilities ────────────────────────────────────────────────────────────
const consoleLogs = [];
const results = [];
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failCount++;
  results.push({ status, name, detail });
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
  return cond;
}

async function screenshot(page, name) {
  await page.screenshot({ path: path.join(SHOTS_DIR, `${name}.png`) });
  console.log(`  📸 ${name}.png`);
}

async function waitForStatus(page, selector, contains, timeout = 30000) {
  await page.waitForFunction(
    ({ sel, text }) => { const e = document.querySelector(sel); return e && e.textContent.includes(text); },
    { sel: selector, text: contains },
    { timeout }
  );
}

// Python Δt cross-check — must match web/compare.html's computeDeltaT.
// Δt(d) = (lap_time_s_session(d) − lap_time_s_ref(d)) × 1000, with the SHM
// lap-boundary artifact filtered out the same way as in JS (see RCA §6).
function pythonDt(sessionPath, sessionSeg, refPath, refSeg, outPath) {
  const code = `
import pyarrow.parquet as pq, json, sys, bisect, math

def build_segs(col):
    segs, prev, start = [], col[0], 0
    for i in range(1, len(col)):
        if col[i] != prev:
            segs.append((prev, start, i)); prev = col[i]; start = i
    segs.append((prev, start, len(col)))
    return segs

def interp(xs, ys, x):
    if x <= xs[0]: return ys[0]
    if x >= xs[-1]: return ys[-1]
    hi = bisect.bisect_right(xs, x); lo = hi - 1
    t = (x - xs[lo]) / (xs[hi] - xs[lo])
    return ys[lo] + t * (ys[hi] - ys[lo])

def resample(dists, vals, max_dist):
    # Stable tie-break by original index keeps time-ordered rows in order
    # within an equal-distance cluster — matches the JS resampler.
    idx = sorted(range(len(dists)), key=lambda i: (dists[i], i))
    xs = [dists[i] for i in idx]
    ys = [vals[i]  for i in idx]
    return [interp(xs, ys, b) for b in range(max_dist + 1)]

def keep_indices(lap_time, lap_dist, track_len):
    half = track_len * 0.5
    out = []
    for i, (t, d) in enumerate(zip(lap_time, lap_dist)):
        if t is not None and d is not None and t < -0.05 and d > half:
            continue
        out.append(i)
    return out

def load_seg(path, seg_idx):
    t = pq.read_table(path, columns=['lap_number','lap_distance_m','lap_time_s'])
    laps  = t.column('lap_number').to_pylist()
    dist  = t.column('lap_distance_m').to_pylist()
    ltime = t.column('lap_time_s').to_pylist()
    segs  = build_segs(laps)
    # trackLen = max maxDist across segments (matches annotateSegments).
    track_len = 0.0
    for (_, a, b) in segs:
        mx = max(dist[a:b])
        if mx > track_len:
            track_len = mx
    seg = segs[seg_idx]
    keep = keep_indices(ltime[seg[1]:seg[2]], dist[seg[1]:seg[2]], track_len)
    d = [dist[seg[1] + k]  for k in keep]
    s = [ltime[seg[1] + k] for k in keep]
    return d, s

sd, ss = load_seg('${sessionPath.replace(/\\/g, '\\\\')}', ${sessionSeg})
rd, rs = load_seg('${refPath.replace(/\\/g, '\\\\')}', ${refSeg})
max_dist = max(max(sd), max(rd))
max_dist = int(math.ceil(max_dist))
s_bins = resample(sd, ss, max_dist)
r_bins = resample(rd, rs, max_dist)

dt = []
for i in range(min(len(s_bins), len(r_bins))):
    dt.append((s_bins[i] - r_bins[i]) * 1000.0)

overlap = {
    'start': max(min(sd), min(rd)),
    'end':   min(math.ceil(max(sd)), math.ceil(max(rd))),
}

json.dump({'dt': dt, 'overlap': overlap, 's_bins': s_bins[:5], 'r_bins': r_bins[:5]}, open('${outPath.replace(/\\/g, '\\\\')}', 'w'))
`;
  const res = spawnSync('python', ['-c', code], { encoding: 'utf8', timeout: 30000 });
  if (res.status !== 0) throw new Error(`python Δt failed: ${res.stderr}`);
}

// ── Main test ─────────────────────────────────────────────────────────────────
async function main() {
  const { server, port } = await startServer();
  const url = `http://127.0.0.1:${port}`;

  console.log(`\n═══ M5 AFK Test Suite ═══`);
  console.log(`URL: ${url}`);
  console.log(`Report: ${REPORT_DIR}\n`);

  const browser = await chromium.launch({ headless: true });

  try {
    // ── SCENARIO 1: Single file, cross-lap comparison ────────────────────────
    console.log('\n════ SCENARIO 1: Single session file (6-lap clean) ════');
    const ctx1 = await browser.newContext();
    const page1 = await ctx1.newPage();
    page1.on('console', msg => {
      const e = `[${msg.type()}] ${msg.text()}`;
      consoleLogs.push(e);
      if (msg.type() === 'error') console.warn(`  ✖ ${e}`);
    });
    page1.on('pageerror', err => {
      consoleLogs.push(`[pageerror] ${err.message}`);
      console.error(`  ✖ PAGE ERROR: ${err.message}`);
    });

    await page1.goto(url);
    await screenshot(page1, 's1_00_initial');

    // Load file
    console.log('  Loading session file…');
    await page1.locator('#load-btn').click();
    await page1.setInputFiles('#file-input', SESSION_CLEAN);
    await waitForStatus(page1, '#session-list .badge.ok', 'rows', 30000);
    const badge1 = await page1.$eval('#session-list .badge.ok', el => el.textContent);
    assert(badge1.includes('rows'), 'S1: file loaded', badge1);
    assert(badge1.includes('6 laps'), 'S1: 6 laps detected', badge1);
    await screenshot(page1, 's1_01_loaded');

    // Check pickers are populated
    const spCount = await page1.$eval('#session-picker', s => s.options.length);
    const rpCount = await page1.$eval('#ref-picker',     s => s.options.length);
    assert(spCount === 6, 'S1: session picker has 6 options', `got ${spCount}`);
    assert(rpCount === 6, 'S1: ref picker has 6 options',     `got ${rpCount}`);

    // Get the store key
    const storeKeys = await page1.evaluate(() => window.__getSessionKeys());
    assert(storeKeys.length === 1, 'S1: store has 1 entry', `got ${storeKeys.length}`);
    const sk = storeKeys[0];

    // Pick lap 3 (seg index 2) as session, lap 5 (seg index 4) as reference
    // Values are "<storeKey>::<segIdx>"
    const val3 = `${sk}::2`;
    const val5 = `${sk}::4`;
    await page1.selectOption('#session-picker', val3);
    await page1.selectOption('#ref-picker', val5);
    await page1.click('#compare-btn');
    await page1.waitForSelector('polyline', { timeout: 10000 });
    await screenshot(page1, 's1_02_compared');

    // Count panels
    const panelCount = await page1.$$eval('.panel-wrap', els => els.length);
    assert(panelCount === 8, 'S1: 8 plot panels rendered', `got ${panelCount}`);

    // Count polylines per panel
    const polylineCounts = await page1.$$eval('.panel-svg', svgs =>
      svgs.map(svg => svg.querySelectorAll('polyline').length)
    );
    console.log('  Polylines per panel:', polylineCounts.join(', '));
    const panelsWithPolylines = polylineCounts.filter(n => n >= 1).length;
    assert(panelsWithPolylines >= 7, 'S1: ≥7 panels have polylines', `got ${panelsWithPolylines}/8`);

    // Check Δt panel exists
    const dtSvg = await page1.$('svg[data-panel-id="dt"]');
    assert(dtSvg !== null, 'S1: Δt panel SVG exists');
    const dtPolylines = await page1.$$eval('svg[data-panel-id="dt"] polyline', els => els.length);
    assert(dtPolylines >= 1, 'S1: Δt panel has polyline', `got ${dtPolylines}`);

    // Cursor / tooltip test
    const svgEl = await page1.$('.panel-svg');
    const svgBox = await svgEl.boundingBox();
    await page1.mouse.move(svgBox.x + svgBox.width / 2, svgBox.y + svgBox.height / 2);
    await page1.waitForTimeout(100);
    const tooltipVisible = await page1.$eval('#tooltip', el => el.style.display !== 'none');
    assert(tooltipVisible, 'S1: tooltip visible on hover');
    const tooltipText = await page1.$eval('#tooltip', el => el.textContent);
    assert(tooltipText.includes('dist:'), 'S1: tooltip contains dist', tooltipText.slice(0, 80));
    assert(tooltipText.includes('speed:'), 'S1: tooltip contains speed', tooltipText.slice(0, 80));
    assert(tooltipText.includes('Δt:'), 'S1: tooltip contains Δt', tooltipText.slice(0, 80));
    await screenshot(page1, 's1_03_cursor_hover');

    // Sector markers — lap 3 has sectors in clean session
    const sectorLines = await page1.$$eval('line[stroke="var(--sector-clr)"]', els => els.length);
    console.log(`  Sector marker lines: ${sectorLines}`);
    assert(sectorLines >= 2, 'S1: sector markers rendered (≥2 lines)', `got ${sectorLines}`);

    // ── Δt cross-check ────────────────────────────────────────────────────────
    console.log('\n  Δt cross-check…');
    try {
      const browserDt = await page1.evaluate(
        ([sk, ss, rk, rs]) => window.__dtDebug(sk, ss, rk, rs),
        [sk, 2, sk, 4]
      );
      const dtPath = path.join(REPORT_DIR, 'python_dt.json');
      pythonDt(SESSION_CLEAN, 2, SESSION_CLEAN, 4, dtPath);
      const { dt: pythonDtArr } = JSON.parse(fs.readFileSync(dtPath, 'utf8'));

      // Compare within the overlap window — bins outside that range carry
      // only the resampler's lap_time_s clamp and don't reflect a real
      // comparison. Both implementations clamp identically so they'd
      // technically agree there too, but the window is where the number
      // matters.
      const overlap = await page1.evaluate(
        ([sk, ss, rk, rs]) => window.__dtDebugOverlap(sk, ss, rk, rs),
        [sk, 2, sk, 4]
      );
      const startIdx = Math.max(0, Math.ceil(overlap.start));
      const endIdx   = Math.min(browserDt.length - 1, pythonDtArr.length - 1, Math.floor(overlap.end));
      let maxDiff = 0, sumDiff = 0, nDiff = 0;
      for (let i = startIdx; i <= endIdx; i++) {
        const d = Math.abs(browserDt[i] - pythonDtArr[i]);
        if (d > maxDiff) maxDiff = d;
        sumDiff += d;
        nDiff++;
      }
      const meanDiff = sumDiff / Math.max(nDiff, 1);
      console.log(`  Δt diff (overlap ${startIdx}..${endIdx}): max=${maxDiff.toFixed(3)} ms, mean=${meanDiff.toFixed(3)} ms`);
      // 5 ms tolerance: the new direct-subtraction method has no cumulative
      // float drift; only float32→float64 conversion noise remains.
      assert(maxDiff < 5, 'S1: Δt max|browser-python| < 5 ms', `got ${maxDiff.toFixed(3)}`);

      const dtSummary = `Δt cross-check (lap 3 vs lap 5, clean session)\n` +
        `Browser bins: ${browserDt.length}\nPython bins:  ${pythonDtArr.length}\n` +
        `Overlap window: ${startIdx}..${endIdx} (${nDiff} bins)\n` +
        `Max |diff|:   ${maxDiff.toFixed(4)} ms\nMean |diff|:  ${meanDiff.toFixed(4)} ms\nThreshold: 5 ms\n` +
        `Result: ${maxDiff < 5 ? 'PASS' : 'FAIL'}\n`;
      fs.writeFileSync(path.join(REPORT_DIR, 'dt_diff.txt'), dtSummary);
      console.log('  Wrote dt_diff.txt');
    } catch (e) {
      assert(false, 'S1: Δt cross-check', e.message);
      console.error('  Δt error:', e.message);
    }

    await ctx1.close();

    // ── SCENARIO 2: Two different files loaded ──────────────────────────────
    console.log('\n════ SCENARIO 2: Two different session files ════');
    const ctx2 = await browser.newContext();
    const page2 = await ctx2.newPage();
    page2.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
    page2.on('pageerror', err => consoleLogs.push(`[pageerror] ${err.message}`));

    await page2.goto(url);

    // Load first file
    await page2.locator('#load-btn').click();
    await page2.setInputFiles('#file-input', SESSION_CLEAN);
    await waitForStatus(page2, '#session-list .badge.ok', '6 laps', 30000);

    // Load second file (restart session)
    await page2.locator('#load-btn').click();
    await page2.setInputFiles('#file-input', SESSION_RESTART);
    // Wait for 2 OK badges (both files loaded)
    await page2.waitForFunction(
      () => document.querySelectorAll('#session-list .badge.ok').length >= 2,
      { timeout: 30000 }
    );

    await screenshot(page2, 's2_01_two_files_loaded');

    // Pickers should have 13 options total (6 + 7)
    const spCount2 = await page2.$eval('#session-picker', s => s.options.length);
    const rpCount2 = await page2.$eval('#ref-picker',     s => s.options.length);
    assert(spCount2 === 13, 'S2: session picker has 13 options (6+7)', `got ${spCount2}`);
    assert(rpCount2 === 13, 'S2: ref picker has 13 options (6+7)',     `got ${rpCount2}`);

    // Pickers should have 2 optgroups (one per file)
    const groupCount = await page2.$eval('#session-picker', s => s.querySelectorAll('optgroup').length);
    assert(groupCount === 2, 'S2: 2 optgroups in picker', `got ${groupCount}`);

    // Cross-file comparison: pick lap 4 from clean session, lap 2 from restart
    const keys2 = await page2.evaluate(() => window.__getSessionKeys());
    assert(keys2.length === 2, 'S2: store has 2 entries', `got ${keys2.length}`);

    const cleanKey2   = keys2.find(k => k.includes('093245'));
    const restartKey2 = keys2.find(k => k.includes('091432'));
    assert(cleanKey2 && restartKey2, 'S2: can identify both file keys');

    if (cleanKey2 && restartKey2) {
      await page2.selectOption('#session-picker', `${cleanKey2}::3`);    // lap 4 of clean
      await page2.selectOption('#ref-picker',     `${restartKey2}::1`);  // lap 2 of restart
      await page2.click('#compare-btn');
      await page2.waitForSelector('polyline', { timeout: 10000 });
      await screenshot(page2, 's2_02_cross_file_compared');
      const panelCount2 = await page2.$$eval('.panel-wrap', els => els.length);
      assert(panelCount2 === 8, 'S2: cross-file comparison renders 8 panels', `got ${panelCount2}`);
    }

    await ctx2.close();

    // ── SCENARIO 3: Restart session ──────────────────────────────────────────
    console.log('\n════ SCENARIO 3: Restart session (7 segments) ════');
    const ctx3 = await browser.newContext();
    const page3 = await ctx3.newPage();
    page3.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
    page3.on('pageerror', err => consoleLogs.push(`[pageerror] ${err.message}`));

    await page3.goto(url);
    await page3.locator('#load-btn').click();
    await page3.setInputFiles('#file-input', SESSION_RESTART);
    await waitForStatus(page3, '#session-list .badge.ok', '7 laps', 30000);

    const rspCount = await page3.$eval('#session-picker', s => s.options.length);
    assert(rspCount === 7, 'S3: restart session has 7 picker options', `got ${rspCount}`);

    // Check chronological order via option text
    const optTexts = await page3.$$eval('#session-picker option', opts =>
      opts.map(o => o.textContent.trim())
    );
    console.log('  Picker options:');
    optTexts.forEach((t, i) => console.log(`    [${i}] ${t.slice(0, 60)}`));
    const firstLapNum = optTexts[0].match(/lap# (\d+)/)?.[1];
    const lastLapNum  = optTexts[optTexts.length - 1].match(/lap# (\d+)/)?.[1];
    assert(firstLapNum === '3', 'S3: first segment is lap# 3', `got ${firstLapNum}`);
    assert(lastLapNum  === '1', 'S3: last segment is lap# 1 (post-restart)', `got ${lastLapNum}`);

    await ctx3.close();

  } finally {
    await browser.close();
    server.close();
  }

  // ── Console log analysis ──────────────────────────────────────────────────
  fs.writeFileSync(path.join(REPORT_DIR, 'console.log'), consoleLogs.join('\n'), 'utf8');
  const errorLines = consoleLogs.filter(l => l.startsWith('[error]') || l.startsWith('[pageerror]'));
  const warnLines  = consoleLogs.filter(l => l.startsWith('[warning]'));
  assert(errorLines.length === 0, 'Console: no browser errors', `${errorLines.length} errors`);

  // ── REPORT.md ─────────────────────────────────────────────────────────────
  const now       = new Date().toISOString();
  const passCount = results.filter(r => r.status === 'PASS').length;
  const lines     = [
    `# M5 Test Report`,
    ``,
    `Generated: ${now}`,
    `Result: **${failCount === 0 ? 'ALL PASS' : failCount + ' FAILURES'}** (${passCount}/${results.length})`,
    ``,
    `## Assertions`,
    ``,
    `| Status | Test | Detail |`,
    `|--------|------|--------|`,
    ...results.map(r => `| ${r.status} | ${r.name} | ${r.detail || ''} |`),
    ``,
    `## Console errors (${errorLines.length})`,
    errorLines.length ? errorLines.map(e => `- \`${e}\``).join('\n') : '(none)',
    ``,
    `## Console warnings (${warnLines.length})`,
    warnLines.length ? warnLines.map(w => `- \`${w}\``).join('\n') : '(none)',
    ``,
    `## Files`,
    `- \`screenshots/\` — browser states`,
    `- \`console.log\` — full browser console`,
    `- \`dt_diff.txt\` — Δt cross-check result`,
  ];
  fs.writeFileSync(path.join(REPORT_DIR, 'REPORT.md'), lines.join('\n'), 'utf8');

  // ── Summary ──────────────────────────────────────────────────────────────
  console.log('\n═══════════════════════════════════');
  console.log(`  ${passCount}/${results.length} assertions passed`);
  if (failCount > 0) {
    console.log(`  ✖ ${failCount} FAILURES`);
    results.filter(r => r.status === 'FAIL').forEach(r =>
      console.log(`    FAIL: ${r.name}${r.detail ? ' [' + r.detail.slice(0,80) + ']' : ''}`)
    );
  } else {
    console.log('  ✔ All assertions passed');
  }
  console.log(`  Report: ${REPORT_DIR}`);
  console.log('═══════════════════════════════════\n');

  process.exit(failCount > 0 ? 1 : 0);
}

main().catch(e => { console.error('Fatal:', e); process.exit(2); });
