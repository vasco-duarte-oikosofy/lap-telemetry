#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Tests for `dev/tools/turn-label-editor.html` (mission turn-label-editor).
 *
 * Two layers:
 *   1. Static contract on the generated file — standalone (no fetch, no external
 *      refs), every track with baked turns present, drag + rotation controls,
 *      and *freshness*: re-running the generator must reproduce the file byte
 *      for byte (the same rule `dist/compare.html` lives under).
 *   2. A real browser run: load the page, switch tracks, drag a corner name,
 *      rotate the map, reload and prove the placement survived.
 *
 * The page is served over HTTP rather than opened as `file://` so localStorage
 * (which the editor uses to remember placements) behaves like it does for a
 * user double-clicking the file in a browser that allows it.
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const { startServer } = require('./lib/test-server');
const { render } = require('./build_turn_label_editor');

const ROOT = path.resolve(__dirname, '..', '..');
const TOOLS_DIR = path.join(ROOT, 'dev', 'tools');
const TOOL = path.join(TOOLS_DIR, 'turn-label-editor.html');
const OUTLINES = path.join(ROOT, 'product/data/track-outlines');

function check(value, label, detail = '') {
  console.log(`[${value ? 'PASS' : 'FAIL'}] ${label}${value || !detail ? '' : ` — ${detail}`}`);
  if (!value) process.exitCode = 1;
}

function outlinesWithTurns() {
  const out = {};
  for (const name of fs.readdirSync(OUTLINES).filter((n) => n.endsWith('.json')).sort()) {
    const outline = JSON.parse(fs.readFileSync(path.join(OUTLINES, name), 'utf8'));
    if (Array.isArray(outline.turns) && outline.turns.length) out[path.basename(name, '.json')] = outline;
  }
  return out;
}

function staticContract() {
  console.log('# static contract');
  check(fs.existsSync(TOOL), 'the generated editor exists');
  if (!fs.existsSync(TOOL)) return false;
  const html = fs.readFileSync(TOOL, 'utf8');
  const source = outlinesWithTurns();
  const slugs = Object.keys(source);

  check(html.startsWith('<!doctype html>'), 'it is a standalone HTML document');
  check(!/<script[^>]+src=/i.test(html), 'no external script tags');
  check(!/<link[^>]+href=/i.test(html), 'no external stylesheets');
  check(!/\bfetch\s*\(/.test(html), 'no fetch() — the page must work from file://');
  check(!/https?:\/\//.test(html.replace(/xmlns="[^"]*"/g, '')), 'no network URLs');
  check(/id="track"/.test(html) && /<select id="track">/.test(html), 'a track picker');
  check(/id="rotation" type="range" min="-180" max="180"/.test(html), 'a rotation slider from -180° to +180°');
  check(/id="rotation-number" type="number"/.test(html), 'a numeric rotation input for exact values');
  check(/pointerdown/.test(html) && /setPointerCapture/.test(html), 'pointer drag handling');
  check(/id="copy"/.test(html) && /id="download"/.test(html), 'copy and download of the placement');
  check(/display_orientation/.test(html), 'the export records TinyPedal\'s display_orientation');
  check(html.split('\n').length <= 437, 'generated file under the 437-line ceiling',
    `${html.split('\n').length} lines`);

  const fresh = render();
  check(html === fresh.html, 'committed file is what the generator produces (no staleness)',
    'run: node dev/scripts/build_turn_label_editor.js');
  check(fresh.skipped.length + Object.keys(fresh.payload.tracks).length ===
        fs.readdirSync(OUTLINES).filter((n) => n.endsWith('.json')).length,
    'every outline file is either included or reported as having no turns');

  const payloadMatch = /const TRACKS = (\{[\s\S]*?\});/.exec(html);
  check(!!payloadMatch, 'the embedded track payload parses out of the page');
  if (!payloadMatch) return false;
  const data = JSON.parse(payloadMatch[1]);
  const dataSlugs = Object.keys(data.tracks);
  check(dataSlugs.length === slugs.length, `all ${slugs.length} tracks with baked turns are embedded`,
    `${dataSlugs.length} embedded`);
  let turnCountOk = true;
  let centreOk = true;
  for (const slug of slugs) {
    const embedded = data.tracks[slug];
    if (!embedded || embedded.turns.length !== source[slug].turns.length) turnCountOk = false;
    const first = source[slug].centerline[0];
    if (!embedded || Math.abs(embedded.centerline[0][0] - first.x) > 0.06 ||
        Math.abs(embedded.centerline[0][1] - first.y) > 0.06) centreOk = false;
  }
  check(turnCountOk, 'every embedded track carries all of its turn anchors');
  check(centreOk, 'centreline survives the round trip to 0.1 m');
  check(dataSlugs.includes('silverstone-national-circuit') && dataSlugs.includes('paul-ricard---elms'),
    'spot check: the two tracks this repo just curated are present');
  return dataSlugs.includes('silverstone-national-circuit');
}

async function browserContract() {
  console.log('\n# browser run');
  const { server, port } = await startServer(TOOLS_DIR);
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1200, height: 820 } });
    const errors = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(String(error)));

    // A clean slate: the editor remembers placements in localStorage.
    await page.goto(`http://127.0.0.1:${port}/turn-label-editor.html`);
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.waitForFunction(() => !!window.__turnLabelEditor);
    check(errors.length === 0, 'page loads with no console errors', errors.join(' | '));

    const options = await page.evaluate(() => Array.from(document.querySelectorAll('#track option')).length);
    check(options === 19, 'track picker lists every track with baked turn anchors', `${options} options`);

    await page.selectOption('#track', 'silverstone-national-circuit');
    const national = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      return { slug: editor.state.slug, turns: editor.outline().turns.length,
               placed: editor.state.placed.length, json: JSON.parse(document.getElementById('json').value) };
    });
    check(national.slug === 'silverstone-national-circuit', 'the select switches the layout');
    check(national.turns === 6 && national.placed === 6, 'all six corner names are drawn',
      `${national.placed} labels`);
    check(national.json.track === 'silverstone-national-circuit' && national.json.lap_length_m > 2600,
      'the JSON panel describes the loaded track');
    check(Object.keys(national.json.labels).length === 6, 'one entry per corner in the export');

    // The canvas actually paints (a blank map would still pass every state check).
    const painted = await page.evaluate(() => {
      const canvas = document.getElementById('canvas');
      const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      let lit = 0;
      for (let i = 0; i < data.length; i += 4) if (data[i] + data[i + 1] + data[i + 2] > 120) lit += 1;
      return lit;
    });
    check(painted > 5000, 'the layout and labels are actually drawn on the canvas', `${painted} lit pixels`);

    // Drag "Copse" by 60 px right / 24 px down and check the offset moved with it.
    const before = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      const label = editor.state.placed.find((item) => item.id === 'copse');
      const rect = document.getElementById('canvas').getBoundingClientRect();
      return { x: rect.left + label.x + label.w / 2, y: rect.top + label.y + label.h / 2,
               offset: editor.setting().offsets.copse || null };
    });
    await page.mouse.move(before.x, before.y);
    await page.mouse.down();
    await page.mouse.move(before.x + 60, before.y + 24, { steps: 6 });
    await page.mouse.up();
    const after = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      return { offset: editor.setting().offsets.copse,
               json: JSON.parse(document.getElementById('json').value).labels.copse };
    });
    check(Array.isArray(after.offset) && after.offset.some((v) => Math.abs(v) > 0.01),
      'dragging a corner name records an offset', JSON.stringify(after.offset));
    check(Math.abs(after.json.dx_m) + Math.abs(after.json.dy_m) > 0.01,
      'the dragged offset appears in the exported JSON', JSON.stringify(after.json));

    // Rotation: 45° via the slider and via the numeric box.
    await page.locator('#rotation').fill('45');
    await page.locator('#rotation').dispatchEvent('input');
    const rotated = await page.evaluate(() => ({
      rotation: window.__turnLabelEditor.setting().rotation,
      orientation: JSON.parse(document.getElementById('json').value).display_orientation,
      label: document.getElementById('rotation-value').textContent,
    }));
    check(rotated.rotation === 45 && rotated.orientation === 45,
      'rotation slider sets 45° and reports it as display_orientation', JSON.stringify(rotated));
    check(rotated.label === '45°', 'the rotation readout follows the slider', rotated.label);
    await page.locator('#rotation-number').fill('-90');
    await page.locator('#rotation-number').dispatchEvent('change');
    const negative = await page.evaluate(() => window.__turnLabelEditor.setting().rotation);
    check(negative === -90, 'the numeric box accepts a negative angle', String(negative));

    // Default layout is a starting point, not a solution: on the two densest
    // layouts (La Sarthe 19 turns, Paul Ricard ELMS 16) the first placement is
    // allowed a few collisions, but most names must start clear so the user has
    // something to drag from rather than a pile.
    const crowded = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      const slugs = Array.from(document.querySelectorAll('#track option')).map((option) => option.value);
      const worst = [], original = editor.state.slug;
      for (const slug of slugs) {
        editor.state.slug = slug;
        editor.setting();
        editor.draw();
        const placed = editor.state.placed;
        const clashing = new Set();
        for (let i = 0; i < placed.length; i += 1) {
          for (let j = i + 1; j < placed.length; j += 1) {
            const a = placed[i], b = placed[j];
            if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) {
              clashing.add(a.id).add(b.id);
            }
          }
        }
        worst.push({ slug, labels: placed.length, clear: placed.length - clashing.size });
      }
      editor.state.slug = original;
      editor.draw();
      return worst;
    });
    const worstCase = crowded.reduce((worst, row) =>
      (row.clear / row.labels < worst.clear / worst.labels ? row : worst), crowded[0]);
    check(crowded.every((row) => row.clear / row.labels >= 0.6),
      'every layout opens with at least 60% of its names clear',
      worstCase.slug + ' ' + worstCase.clear + '/' + worstCase.labels);

    // Labels stay attached to their corners: the offset is map-space metres, so
    // it must not drift with rotation even though the fitted scale does change.
    const attached = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      const turn = editor.outline().turns.find((item) => item.id === 'becketts');
      const metres = [];
      for (const angle of [0, 30, -120]) {
        editor.setting().rotation = angle;
        editor.draw();
        const [ax, ay] = editor.toScreen(turn.x, turn.y);
        const label = editor.state.placed.find((item) => item.id === 'becketts');
        const pixels = Math.hypot(label.x + label.w / 2 - ax, label.y + label.h / 2 - ay);
        metres.push(pixels / editor.state.view.scale);
      }
      return { metres };
    });
    const spread = Math.max(...attached.metres) - Math.min(...attached.metres);
    check(spread < 0.1, 'a label keeps its offset in metres at every rotation',
      attached.metres.map((d) => d.toFixed(2)).join(' / ') + ' m');

    // Persistence: a reload keeps the placement and the rotation. Set the angle
    // through the UI so it is actually saved (the measurement above bypassed it).
    await page.locator('#rotation-number').fill('-120');
    await page.locator('#rotation-number').dispatchEvent('change');
    await page.reload();
    await page.waitForFunction(() => !!window.__turnLabelEditor);
    const restored = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      return { slug: editor.state.slug, rotation: editor.setting().rotation,
               offset: editor.setting().offsets.copse || null };
    });
    check(restored.slug === 'silverstone-national-circuit' && restored.rotation === -120,
      'the last track and rotation survive a reload', JSON.stringify(restored));
    check(Array.isArray(restored.offset) && restored.offset.some((v) => Math.abs(v) > 0.01),
      'the dragged placement survives a reload', JSON.stringify(restored.offset));

    // Reset puts it back on the corner and clears the rotation.
    await page.locator('#reset-track').click();
    const reset = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      return { rotation: editor.setting().rotation, offsets: Object.keys(editor.setting().offsets).length };
    });
    check(reset.rotation === 0 && reset.offsets === 0, 'Reset clears this track\'s placement',
      JSON.stringify(reset));

    check(errors.length === 0, 'no console errors after the whole run', errors.join(' | '));
  } finally {
    await browser.close();
    server.close();
  }
}

(async () => {
  if (staticContract()) await browserContract();
})().catch((error) => {
  console.error(error.stack || String(error));
  process.exitCode = 1;
});
