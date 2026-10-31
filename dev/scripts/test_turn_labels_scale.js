#!/usr/bin/env node
// Every packaged outline, planned at the compare app's real map sizes.
//
// The unit test proves the rule on fixtures; this one proves the shipped data
// still works at the size the product draws, which is where "the font is too
// small" and "labels vanished on the dense tracks" show up. It runs the REAL
// planner with REAL canvas metrics in a real browser, but needs no session:
// it plans against the packaged outlines directly.
//
// [PASS]/[FAIL] protocol per AGENTS.md.

const path = require('path');
const { chromium } = require('playwright');
const { startServer } = require('./lib/test-server');

const ROOT = path.resolve(__dirname, '..', '..');

const VIEWS = [
  // [cssWidth, cssHeight] of the map canvas at three real window sizes
  { w: 500, h: 454, name: 'narrow window' },
  { w: 650, h: 574, name: 'default 1400x1000' },
  { w: 910, h: 622, name: '1920x1080' },
];

let failures = 0;
function check(name, ok, detail = '') {
  console.log(`  ${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!ok) failures += 1;
}

(async () => {
  const { server, port } = await startServer(path.join(ROOT, 'product', 'web'));
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(`http://127.0.0.1:${port}/compare.html`);
  await page.waitForTimeout(300);

  // Plan every outline at every viewport, inside the page so the planner and the
  // canvas metrics are the shipped ones.
  const results = await page.evaluate(async (views) => {
    const { planTurnLabels, TURN_LABEL_CONFIG } = await import('/js/turnLabels.js');
    const manifest = await import('/js/trackOutlineManifest.js');
    const { canvasMeasure } = await import('/js/turnLabelsRender.js');
    const ctx = document.createElement('canvas').getContext('2d');

    function bboxOf(outline) {
      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      for (const p of outline.centerline) {
        minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
        minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
      }
      return { minX, maxX, minY, maxY };
    }
    // Same fit-to-view as fitToView()/pipeline PAD 20: preserve aspect, centre.
    function transformFor(box, w, h) {
      const availW = w - 40;
      const availH = h - 40;
      const bw = box.maxX - box.minX || 1;
      const bh = box.maxY - box.minY || 1;
      const s = Math.min(availW / bw, availH / bh);
      const ox = 20 + (availW - bw * s) / 2;
      const oy = 20 + (availH - bh * s) / 2;
      return { toMapX: x => ox + (x - box.minX) * s, toMapZ: y => oy + (box.maxY - y) * s };
    }

    const seen = new Set();
    const rows = [];
    for (const name of manifest.availableOutlineTracks()) {
      const outline = manifest.findOutlineByTrackName(name);
      if (!outline || seen.has(outline) || !outline.turns?.length) continue;
      seen.add(outline);
      for (const v of views) {
        const mapSize = Math.min(v.w, v.h);
        const t = transformFor(bboxOf(outline), v.w, v.h);
        const plan = planTurnLabels({
          turns: outline.turns, ...t, mapSize, mapWidth: v.w, mapHeight: v.h,
          measure: canvasMeasure(ctx),
        });
        let overlaps = 0;
        for (let i = 0; i < plan.labels.length; i++) {
          for (let j = i + 1; j < plan.labels.length; j++) {
            const a = plan.labels[i], b = plan.labels[j];
            if (Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) > 0 &&
                Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) > 0) overlaps += 1;
          }
        }
        const outside = plan.labels.filter(l =>
          l.x < 0 || l.y < 0 || l.x + l.w > v.w || l.y + l.h > v.h).length;
        rows.push({
          track: name, view: v.name, turns: outline.turns.length,
          labelled: plan.labels.length,
          // A bare "T5" is correct when the coaching model has no name for the
          // corner, so only turns that DO have a name are expected to show one.
          namedTurns: outline.turns.filter(t => t.short_name || t.name).length,
          named: plan.labels.filter(l => l.text.includes(' ')).length,
          overlaps, outside,
          fontSize: +plan.fontSize.toFixed(2),
          configFontMax: TURN_LABEL_CONFIG.fontMax,
        });
      }
    }
    return { rows, size250: +(250 * TURN_LABEL_CONFIG.fontRatio).toFixed(2) };
  }, VIEWS);
  await browser.close();
  server.close();

  check('outlines were found', results.rows.length > 0, `${results.rows.length} plans`);

  for (const view of VIEWS) {
    const rows = results.rows.filter(r => r.view === view.name);
    const total = rows.reduce((n, r) => n + r.turns, 0);
    const labelled = rows.reduce((n, r) => n + r.labelled, 0);
    const incomplete = rows.filter(r => r.labelled !== r.turns).map(r => r.track);
    check(`${view.name}: every turn is labelled`, incomplete.length === 0,
      `${labelled}/${total} labels${incomplete.length ? ' — missing on ' + incomplete.join(', ') : ''}`);
    check(`${view.name}: no label overlaps another`,
      rows.every(r => r.overlaps === 0), `${rows.reduce((n, r) => n + r.overlaps, 0)} pairs`);
    check(`${view.name}: every label stays on the map`,
      rows.every(r => r.outside === 0), `${rows.reduce((n, r) => n + r.outside, 0)} outside`);
    const sizes = [...new Set(rows.map(r => r.fontSize))];
    check(`${view.name}: type scales with the panel`, sizes.length === 1 && sizes[0] > 9,
      `${sizes.join(',')} px`);
  }

  // Names survive at the product size: the whole point is "T5 Becketts", not "T5".
  const named = results.rows.filter(r => r.view === 'default 1400x1000');
  const namedTotal = named.reduce((n, r) => n + r.namedTurns, 0);
  const namedCount = named.reduce((n, r) => n + r.named, 0);
  check('every named turn shows its name at the product size', namedCount === namedTotal,
    `${namedCount}/${namedTotal} named turns, rest are unnamed corners`);

  // Small maps (the tinypedal port) must keep the reviewed sizes.
  check('a 250 px map is still 5.75 px', Math.abs(results.size250 - 5.75) < 1e-9,
    `${results.size250} px`);

  console.log(`\n${failures === 0 ? 'RESULT: PASS' : 'RESULT: FAIL'}`);
  process.exit(failures === 0 ? 0 : 1);
})().catch(err => {
  console.error('FAIL unexpected error —', err.message);
  console.log('RESULT: FAIL');
  process.exit(1);
});
