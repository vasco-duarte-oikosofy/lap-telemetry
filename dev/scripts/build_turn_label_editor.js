#!/usr/bin/env node
'use strict';

/**
 * Build `dev/tools/turn-label-editor.html` from the template + every track outline.
 *
 * A `file://` page cannot `fetch()` the outlines, so the track data is inlined.
 * Only what the editor draws is inlined — slug, names, `lap_length_m`, the
 * centreline and the turn anchors — rounded to 0.1 m. The three outline files
 * with per-point boundaries are ~250 KB each; the payload here is ~600 KB for
 * all 30 layouts, which keeps the tool a single double-clickable file.
 *
 * Usage:
 *   node dev/scripts/build_turn_label_editor.js            # write the tool
 *   node dev/scripts/build_turn_label_editor.js --out FILE  # write elsewhere (tests)
 *   node dev/scripts/build_turn_label_editor.js --check     # verify it is current
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const OUTLINES = path.join(ROOT, 'product/data/track-outlines');
const TEMPLATE = path.join(ROOT, 'dev/tools/turn-label-editor.template.html');
const TARGET = path.join(ROOT, 'dev/tools/turn-label-editor.html');
const PLACEHOLDER = '/*__TRACK_DATA__*/';

const round1 = (value) => Math.round(Number(value) * 10) / 10;

function buildTrack(fileName, outline) {
  const turns = (outline.turns || []).map((turn) => ({
    id: turn.id,
    number: turn.number,
    name: turn.name,
    short_name: turn.short_name || null,
    apex_s_m: round1(turn.apex_s_m),
    x: round1(turn.x),
    y: round1(turn.y),
    outward: Array.isArray(turn.outward) ? turn.outward.map((v) => Math.round(Number(v) * 1000) / 1000) : null,
    tangent: Array.isArray(turn.tangent) ? turn.tangent.map((v) => Math.round(Number(v) * 1000) / 1000) : null,
  }));
  if (!turns.length) return null;
  return {
    track_name: outline.track_name || fileName,
    layout: outline.layout_name || null,
    lap_length_m: round1(outline.lap_length_m || 0),
    centerline: (outline.centerline || []).map((point) => [round1(point.x), round1(point.y)]),
    turns,
  };
}

function buildPayload() {
  const files = fs.readdirSync(OUTLINES).filter((name) => name.endsWith('.json')).sort();
  const tracks = {};
  const skipped = [];
  for (const fileName of files) {
    const outline = JSON.parse(fs.readFileSync(path.join(OUTLINES, fileName), 'utf8'));
    if (!outline.centerline || !outline.turns || !outline.turns.length) {
      skipped.push(fileName);
      continue;
    }
    const slug = path.basename(fileName, '.json');
    tracks[slug] = buildTrack(slug, outline);
  }
  return { payload: { built_from: 'product/data/track-outlines', tracks }, skipped, files };
}

function render() {
  const template = fs.readFileSync(TEMPLATE, 'utf8');
  if (!template.includes(PLACEHOLDER)) throw new Error(`template is missing ${PLACEHOLDER}`);
  const { payload, skipped, files } = buildPayload();
  const data = JSON.stringify(payload);
  const html = template.replace(PLACEHOLDER, data);
  return { html, payload, skipped, count: files.length - skipped.length };
}

function main(argv) {
  const args = argv.slice(2);
  const outIndex = args.indexOf('--out');
  const target = outIndex >= 0 ? path.resolve(args[outIndex + 1]) : TARGET;
  const { html, payload, skipped, count } = render();
  const trackCount = Object.keys(payload.tracks).length;
  const lines = html.split('\n').length;

  if (args.includes('--check')) {
    const current = fs.existsSync(target) ? fs.readFileSync(target, 'utf8') : '';
    if (current !== html) {
      console.error(`STALE ${path.relative(ROOT, target)} — run: node dev/scripts/build_turn_label_editor.js`);
      return 1;
    }
    console.log(`ok ${path.relative(ROOT, target)}: ${trackCount} tracks, ${lines} lines`);
    return 0;
  }

  fs.writeFileSync(target, html);
  console.log(`wrote ${path.relative(ROOT, target)} — ${trackCount} track(s) with baked turn anchors of ${
    count} outline file(s)${skipped.length ? ` (${skipped.length} have no turns)` : ''}, ${
    (html.length / 1024).toFixed(0)} KB, ${lines} lines`);
  if (lines > 437) console.error(`FAIL: ${lines} lines exceeds the 437-line ceiling`);
  return lines > 437 ? 1 : 0;
}

if (require.main === module) process.exit(main(process.argv));
module.exports = { render, buildPayload };
