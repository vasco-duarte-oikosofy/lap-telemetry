#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Tests for the turn label editor (`dev/tools/turn-label-editor.html`).
 *
 * Three layers:
 *   1. Static contract — three small files (html + app + generated data), no
 *      network, no `fetch()`, and the data file must be exactly what the
 *      generator produces (the same freshness rule `dist/compare.html` lives
 *      under).
 *   2. A real browser run over HTTP: track switch, drag *directions*, rotation,
 *      persistence, reset, import of an exported placement (including the v1
 *      Y-mirror repair) and the shipped Imola preset.
 *   3. A `file://` smoke run, because the whole point is double-clicking the
 *      file — a page that only works behind a server would be useless here.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const { startServer } = require('./lib/test-server');
const { render } = require('./build_turn_label_editor');

const ROOT = path.resolve(__dirname, '..', '..');
const TOOLS = path.join(ROOT, 'dev', 'tools');
const OUTLINES = path.join(ROOT, 'product/data/track-outlines');
const PRESETS = path.join(TOOLS, 'turn-label-presets.json');
const files = {
  html: path.join(TOOLS, 'turn-label-editor.html'),
  app: path.join(TOOLS, 'turn-label-editor.js'),
  ui: path.join(TOOLS, 'turn-label-editor-ui.js'),
  data: path.join(TOOLS, 'turn-label-data.js'),
};
let failures = 0;

function check(value, label, detail = '') {
  console.log(`[${value ? 'PASS' : 'FAIL'}] ${label}${value || !detail ? '' : ` — ${detail}`}`);
  if (!value) failures += 1;
}

function outlinesWithTurns() {
  const out = {};
  for (const name of fs.readdirSync(OUTLINES).filter((n) => n.endsWith('.json')).sort()) {
    const outline = JSON.parse(fs.readFileSync(path.join(OUTLINES, name), 'utf8'));
    if (Array.isArray(outline.turns) && outline.turns.length) out[path.basename(name, '.json')] = outline;
  }
  return out;
}

function readEmbedded(file, name) {
  const match = new RegExp(`window\\.${name} = (\\{.*?\\});`).exec(fs.readFileSync(file, 'utf8'));
  return match ? JSON.parse(match[1]) : null;
}

function staticContract() {
  console.log('# static contract');
  for (const [key, file] of Object.entries(files)) {
    check(fs.existsSync(file), `the ${key} file exists: ${path.basename(file)}`);
  }
  const html = fs.readFileSync(files.html, 'utf8');
  const source = outlinesWithTurns();
  const slugs = Object.keys(source);

  check(html.startsWith('<!doctype html>'), 'it is a standalone HTML document');
  check((html.match(/<script src="/g) || []).length === 4,
    'four relative script tags (data, app, preview, ui)');
  check(!/https?:\/\//.test(html.replace(/xmlns="[^"]*"/g, '')), 'no network URLs in the page');
  check(!/\bfetch\s*\(/.test(html + fs.readFileSync(files.app, 'utf8')), 'no fetch() — must work from file://');
  check(!/type="module"/.test(html), 'classic scripts only (ES modules do not load from file://)');
  check(/id="track"/.test(html) && /<select id="track">/.test(html), 'a track picker');
  check(/id="rotation" type="range" min="-180" max="180"/.test(html), 'rotation slider -180°…+180°');
  check(/id="rotation-number" type="number"/.test(html), 'numeric rotation input');
  check(/id="import-file" type="file"/.test(html), 'an import control for a placement JSON');
  check(/id="copy"/.test(html) && /id="download"/.test(html), 'copy and download of the placement');

  for (const [key, file] of Object.entries(files)) {
    const lines = fs.readFileSync(file, 'utf8').split('\n').length;
    check(lines <= 437, `${key} file under the 437-line ceiling`, `${lines} lines`);
  }

  const built = render();
  check(fs.readFileSync(files.data, 'utf8') === built.text,
    'the committed data file is what the generator produces (no staleness)',
    'run: node dev/scripts/build_turn_label_editor.js');

  const data = readEmbedded(files.data, 'TURN_LABEL_DATA');
  const presets = readEmbedded(files.data, 'TURN_LABEL_PRESETS');
  check(!!data && Object.keys(data.tracks).length === slugs.length,
    `all ${slugs.length} tracks with baked turns are embedded`);
  let anchorsOk = true;
  for (const slug of slugs) {
    if (!data.tracks[slug] || data.tracks[slug].turns.length !== source[slug].turns.length) anchorsOk = false;
  }
  check(anchorsOk, 'every embedded track carries all of its turn anchors');
  check(!!presets && Object.keys(presets).length >= 1, 'shipped placements are embedded',
    JSON.stringify(Object.keys(presets || {})));
  check(JSON.stringify(presets) === JSON.stringify(JSON.parse(fs.readFileSync(PRESETS, 'utf8'))),
    'the embedded presets match dev/tools/turn-label-presets.json');
  return slugs.length;
}

async function browserContract() {
  console.log('\n# browser run');
  const { server, port } = await startServer(TOOLS);
  const browser = await chromium.launch();
  const errors = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(String(error)));
    await page.goto(`http://127.0.0.1:${port}/turn-label-editor.html`);
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.waitForFunction(() => !!window.__turnLabelEditor);
    check(errors.length === 0, 'page loads with no console errors', errors.join(' | '));

    const options = await page.evaluate(() => document.querySelectorAll('#track option').length);
    check(options === 19, 'track picker lists every track with baked turn anchors', `${options} options`);

    // --- the shipped Imola placement (the driver's own, exported pre-fix) ---
    await page.selectOption('#track', 'autodromo-enzo-e-dino-ferrari');
    const imola = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      editor.draw();
      const placed = editor.state.placed;
      let overlaps = 0;
      for (let i = 0; i < placed.length; i += 1) {
        for (let j = i + 1; j < placed.length; j += 1) {
          const a = placed[i], b = placed[j];
          if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) overlaps += 1;
        }
      }
      return { rotation: editor.setting().rotation, labels: placed.length, overlaps,
               offsets: Object.keys(editor.setting().offsets).length };
    });
    check(imola.rotation === 96, 'Imola opens at the driver\'s rotation in TinyPedal\'s sign (+96°)',
      String(imola.rotation));
    check(imola.labels === 11 && imola.offsets === 11, 'all 11 Imola names carry the placed offset',
      `${imola.offsets} offsets`);
    check(imola.overlaps === 0, 'the shipped Imola placement has no overlapping labels',
      `${imola.overlaps} pairs`);

    // --- drag directions (regression: vertical used to be inverted) ---
    await page.selectOption('#track', 'silverstone-national-circuit');
    async function dragCopse(dx, dy) {
      const start = await page.evaluate(() => {
        const editor = window.__turnLabelEditor;
        editor.setting().offsets = {};
        editor.setting().rotation = 0;
        editor.draw();
        const label = editor.state.placed.find((item) => item.id === 'copse');
        const rect = document.getElementById('canvas').getBoundingClientRect();
        return { x: rect.left + label.x + label.w / 2, y: rect.top + label.y + label.h / 2,
                 box: { x: label.x, y: label.y } };
      });
      await page.mouse.move(start.x, start.y);
      await page.mouse.down();
      await page.mouse.move(start.x + dx, start.y + dy, { steps: 5 });
      await page.mouse.up();
      const end = await page.evaluate(() => {
        const editor = window.__turnLabelEditor;
        const label = editor.state.placed.find((item) => item.id === 'copse');
        return { box: { x: label.x, y: label.y }, offset: editor.setting().offsets.copse };
      });
      return { start, end };
    }
    const down = await dragCopse(0, 40);
    check(down.end.box.y > down.start.box.y + 20,
      'dragging DOWN moves the label down the screen',
      `${down.start.box.y.toFixed(0)} -> ${down.end.box.y.toFixed(0)} px`);
    check(down.end.offset[1] < -1, 'and records a negative dy in map space (Y is up there)',
      JSON.stringify(down.end.offset.map((v) => Math.round(v))));
    const right = await dragCopse(40, 0);
    check(right.end.box.x > right.start.box.x + 20,
      'dragging RIGHT moves the label right the screen',
      `${right.start.box.x.toFixed(0)} -> ${right.end.box.x.toFixed(0)} px`);
    check(right.end.offset[0] > 1, 'and records a positive dx', JSON.stringify(right.end.offset.map((v) => Math.round(v))));

    // --- rotation ---
    await page.locator('#rotation').fill('45');
    await page.locator('#rotation').dispatchEvent('input');
    const rotated = await page.evaluate(() => ({
      rotation: window.__turnLabelEditor.setting().rotation,
      orientation: JSON.parse(document.getElementById('json').value).display_orientation,
      version: JSON.parse(document.getElementById('json').value).version }));
    check(rotated.rotation === 45 && rotated.orientation === 45,
      'rotation slider sets 45° and exports it as display_orientation', JSON.stringify(rotated));
    check(rotated.version === 3, 'exports are version 3 (TinyPedal rotation convention)',
      String(rotated.version));

    // --- import: v2 round trip and v1 repair ---
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'turn-label-'));
    const legacy = path.join(dir, 'legacy.json');
    fs.writeFileSync(legacy, JSON.stringify({
      tool: 'turn-label-editor', version: 1, track: 'silverstone-national-circuit',
      display_orientation: 0, label_text: 'number-name', font_px: 13,
      labels: { copse: { dx_m: 10, dy_m: 50 } },
    }));
    await page.locator('#import-file').setInputFiles(legacy);
    const imported = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      return { track: editor.state.slug, offset: editor.setting().offsets.copse,
               rotation: editor.setting().rotation, status: document.getElementById('status').textContent };
    });
    check(imported.track === 'silverstone-national-circuit' && imported.rotation === 0,
      'import switches to the file\'s track and rotation', JSON.stringify(imported.track));
    check(Math.abs(imported.offset[0] - 10) < 0.01 && Math.abs(imported.offset[1] + 50) < 0.01,
      'a v1 export is repaired: dy flips sign (labels used to be drawn with a flipped Y)',
      JSON.stringify(imported.offset));

    const bad = path.join(dir, 'bad.json');
    fs.writeFileSync(bad, JSON.stringify({ tool: 'something-else', labels: {} }));
    await page.locator('#import-file').setInputFiles(bad);
    const rejected = await page.evaluate(() => document.getElementById('status').textContent);
    check(/import failed/.test(rejected), 'a foreign JSON is refused with a visible reason', rejected);

    // --- TinyPedal preview tab ---
    await page.selectOption('#track', 'autodromo-enzo-e-dino-ferrari');
    const editorBearings = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      editor.setTab('edit');
      const out = {};
      for (const label of editor.state.placed) {
        const turn = editor.outline().turns.find((item) => item.id === label.id);
        const [ax, ay] = editor.toScreen(turn.x, turn.y);
        out[label.id] = Math.atan2(label.y + label.h / 2 - ay, label.x + label.w / 2 - ax) * 180 / Math.PI;
      }
      return out;
    });
    await page.locator('#tab-preview').click();
    const preview = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      const p = editor.state.preview;
      const bearings = {};
      for (const label of p.drawn) {
        bearings[label.id] = Math.atan2(label.y - label.anchorY, label.x - label.anchorX) * 180 / Math.PI;
      }
      return { status: document.getElementById('status').textContent, angle: p.angle, source: p.source,
               placed: p.placed, dropped: p.dropped, anchors: p.anchors, drawn: p.drawn.length,
               bearings, rotation: editor.setting().rotation,
               orientation: JSON.parse(document.getElementById('json').value).display_orientation };
    });
    check(/TinyPedal preview/.test(preview.status), 'the preview tab renders and reports itself',
      preview.status.split(String.fromCharCode(10))[0]);
    check(/Enzo e Dino Ferrari\.svg/.test(preview.source), "the preview uses the recorded TinyPedal map",
      preview.source);
    check(preview.angle === preview.rotation && preview.orientation === preview.rotation,
      'the preview rotates by exactly the exported display_orientation',
      `${preview.angle} / ${preview.orientation}`);
    check(preview.drawn === 11 && preview.anchors === 11, 'all 11 corners are drawn in the preview',
      `${preview.drawn}/${preview.anchors}`);
    check(/from your placement: 11/.test(preview.status), 'every label comes from the placement, not the fallback',
      preview.status.split(String.fromCharCode(10)).pop());
    const angles = Object.keys(editorBearings).filter((id) => id in preview.bearings)
      .map((id) => Math.abs(((preview.bearings[id] - editorBearings[id] + 540) % 360) - 180));
    check(angles.length === 11 && Math.max(...angles) < 25,
      'each label sits the same way round its corner in both tabs (rotation conventions agree)',
      `worst ${Math.max(...angles).toFixed(0)}° over ${angles.length} corners`);
    await page.locator('#tab-edit').click();
    const backToEdit = await page.evaluate(() => window.__turnLabelEditor.view.tab);
    check(backToEdit === 'edit', 'the edit tab comes back', backToEdit);

    // --- persistence + reset ---
    await page.reload();
    await page.waitForFunction(() => !!window.__turnLabelEditor);
    await page.selectOption('#track', 'silverstone-national-circuit');
    const restored = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      return { track: editor.state.slug, offset: editor.setting().offsets.copse };
    });
    check(restored.track === 'silverstone-national-circuit' && Array.isArray(restored.offset),
      'the imported placement survives a reload', JSON.stringify(restored));
    await page.locator('#reset-track').click();
    const reset = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      return { offsets: Object.keys(editor.setting().offsets).length, rotation: editor.setting().rotation };
    });
    check(reset.offsets === 0 && reset.rotation === 0, 'Reset clears a track that has no shipped preset',
      JSON.stringify(reset));
    await page.selectOption('#track', 'autodromo-enzo-e-dino-ferrari');
    await page.locator('#reset-track').click();
    const presetReset = await page.evaluate(() => {
      const editor = window.__turnLabelEditor;
      return { rotation: editor.setting().rotation, offsets: Object.keys(editor.setting().offsets).length };
    });
    check(presetReset.rotation === 96 && presetReset.offsets === 11,
      'Reset on a track WITH a shipped preset restores that preset, not a blank layout',
      JSON.stringify(presetReset));

    // Every layout must open with most names clear, or there is nothing to drag.
    const crowded = await page.evaluate(() => {
      const editor = window.__turnLabelEditor, original = editor.state.slug, worst = [];
      for (const slug of Array.from(document.querySelectorAll('#track option')).map((o) => o.value)) {
        editor.state.slug = slug;
        editor.setting();
        editor.draw();
        const placed = editor.state.placed, clashing = new Set();
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
    const tightest = crowded.reduce((worst, row) =>
      (row.clear / row.labels < worst.clear / worst.labels ? row : worst), crowded[0]);
    check(crowded.every((row) => row.clear / row.labels >= 0.6),
      'every layout opens with at least 60% of its names clear',
      `${tightest.slug} ${tightest.clear}/${tightest.labels}`);

    const painted = await page.evaluate(() => {
      const canvas = document.getElementById('canvas');
      const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      let lit = 0;
      for (let i = 0; i < data.length; i += 4) if (data[i] + data[i + 1] + data[i + 2] > 120) lit += 1;
      return lit;
    });
    check(painted > 5000, 'the layout and labels are painted on the canvas', `${painted} lit pixels`);
    check(errors.length === 0, 'no console errors after the whole run', errors.join(' | '));
  } finally {
    await browser.close();
    server.close();
  }
}

async function fileUrlSmoke() {
  console.log('\n# file:// smoke (double-click)');
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1200, height: 800 } });
    const errors = [];
    page.on('pageerror', (error) => errors.push(String(error)));
    await page.goto(pathToFileURL(files.html).href);
    await page.waitForFunction(() => !!window.__turnLabelEditor, { timeout: 10000 });
    const booted = await page.evaluate(() => ({
      options: document.querySelectorAll('#track option').length,
      labels: window.__turnLabelEditor.state.placed.length,
      slug: window.__turnLabelEditor.state.slug,
    }));
    check(booted.options === 19 && booted.labels > 0,
      'the page boots straight from file:// with its data and labels',
      JSON.stringify(booted));
    check(errors.length === 0, 'no page errors loading from file://', errors.join(' | '));
  } finally {
    await browser.close();
  }
}

(async () => {
  const tracks = staticContract();
  if (tracks) {
    await browserContract();
    await fileUrlSmoke();
  }
  console.log(failures ? `\nFAILED — ${failures} failure(s)` : '\nALL PASS');
  if (failures) process.exitCode = 1;
})().catch((error) => {
  console.error(error.stack || String(error));
  process.exitCode = 1;
});
