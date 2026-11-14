#!/usr/bin/env node
'use strict';

/**
 * Build `dev/tools/turn-label-data.js` for the turn label editor.
 *
 * A `file://` page cannot `fetch()` the outlines, so every track the editor can
 * show is inlined here as plain data (classic script, no module, no network):
 *
 *   window.TURN_LABEL_DATA     — slug -> { track_name, layout, lap_length_m,
 *                                  centerline: [[x, y]], turns: [...] }
 *   window.TURN_LABEL_PRESETS  — slug -> a shipped placement, copied verbatim
 *                                  from dev/tools/turn-label-presets.json
 *
 * Only what the editor draws is inlined, rounded to 0.1 m. The three outline
 * files with per-point boundaries are ~250 KB each; this payload is ~200 KB for
 * every layout with turns.
 *
 * Usage:
 *   node dev/scripts/build_turn_label_editor.js            # write the data file
 *   node dev/scripts/build_turn_label_editor.js --out FILE  # write elsewhere (tests)
 *   node dev/scripts/build_turn_label_editor.js --check     # verify it is current
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const OUTLINES = path.join(ROOT, 'product/data/track-outlines');
const PRESETS = path.join(ROOT, 'dev/tools/turn-label-presets.json');
// The sibling TinyPedal checkout: its recorded map SVG (the shape the live
// widget actually draws) and the packaged turn labels (the s_frac it anchors on).
const TINYPEDAL = path.resolve(ROOT, '..', 'tinypedal');
const TP_MAPS = path.join(TINYPEDAL, 'trackmap');
const TP_LABELS = path.join(TINYPEDAL, 'tinypedal/data/turn_labels');
const TARGET = path.join(ROOT, 'dev/tools/turn-label-data.js');
const CEILING = 437;

const round1 = (value) => Math.round(Number(value) * 10) / 10;
const round3 = (value) => Math.round(Number(value) * 1000) / 1000;

function readTinypedal(trackName) {
  if (!trackName) return null;
  const svgPath = path.join(TP_MAPS, `${trackName}.svg`);
  if (!fs.existsSync(svgPath)) return null;
  const svg = fs.readFileSync(svgPath, 'utf8');
  const points = /<polyline id="map"[^>]*points="([^"]+)"/.exec(svg);
  if (!points) return null;
  const map = points[1].trim().split(/\s+/).map((pair) => pair.split(',').map(Number))
    .filter((pair) => pair.length === 2 && pair.every(Number.isFinite));
  if (map.length < 2) return null;
  let length = 0;
  for (let i = 1; i < map.length; i += 1) {
    length += Math.hypot(map[i][0] - map[i - 1][0], map[i][1] - map[i - 1][1]);
  }
  const labelPath = path.join(TP_LABELS, `${trackName}.turns.json`);
  const packaged = fs.existsSync(labelPath) ? JSON.parse(fs.readFileSync(labelPath, 'utf8')) : null;
  return {
    map: map.map(([x, y]) => [round1(x), round1(y)]),
    length: round1(length),
    s_frac: packaged && Array.isArray(packaged.turns)
      ? packaged.turns.map((turn) => Math.round(Number(turn.s_frac) * 1e6) / 1e6) : null,
    source: path.basename(svgPath),
  };
}

function buildTrack(outline) {
  const turns = (outline.turns || []).map((turn) => ({
    id: turn.id,
    number: turn.number,
    name: turn.name,
    short_name: turn.short_name || null,
    apex_s_m: round1(turn.apex_s_m),
    x: round1(turn.x),
    y: round1(turn.y),
    outward: Array.isArray(turn.outward) ? turn.outward.map(round3) : null,
    tangent: Array.isArray(turn.tangent) ? turn.tangent.map(round3) : null,
  }));
  if (!turns.length) return null;
  const track = {
    track_name: outline.track_name || '',
    layout: outline.layout_name || null,
    lap_length_m: round1(outline.lap_length_m || 0),
    centerline: (outline.centerline || []).map((point) => [round1(point.x), round1(point.y)]),
    turns,
  };
  // Only when the packaged fractions line up with the outline's turn order.
  const tinypedal = readTinypedal(track.track_name);
  if (tinypedal && tinypedal.s_frac && tinypedal.s_frac.length === turns.length) {
    track.tinypedal = tinypedal;
  } else if (tinypedal) {
    track.tinypedal = { map: tinypedal.map, length: tinypedal.length, s_frac: null,
                        source: tinypedal.source };
  }
  return track;
}

function buildPayload() {
  const files = fs.readdirSync(OUTLINES).filter((name) => name.endsWith('.json')).sort();
  const tracks = {};
  const skipped = [];
  for (const fileName of files) {
    const outline = JSON.parse(fs.readFileSync(path.join(OUTLINES, fileName), 'utf8'));
    const track = outline.centerline && outline.turns && outline.turns.length
      ? buildTrack(outline) : null;
    if (!track) { skipped.push(fileName); continue; }
    tracks[path.basename(fileName, '.json')] = track;
  }
  const presets = fs.existsSync(PRESETS) ? JSON.parse(fs.readFileSync(PRESETS, 'utf8')) : {};
  for (const slug of Object.keys(presets)) {
    if (!tracks[slug]) throw new Error(`preset for unknown track "${slug}" in ${path.basename(PRESETS)}`);
  }
  return { tracks, presets, skipped, count: files.length };
}

function render() {
  const { tracks, presets, skipped, count } = buildPayload();
  const text = [
    '/* GENERATED by dev/scripts/build_turn_label_editor.js — do not edit by hand.',
    '   Source: product/data/track-outlines/*.json + dev/tools/turn-label-presets.json */',
    'window.TURN_LABEL_DATA = ' + JSON.stringify({ built_from: 'product/data/track-outlines', tracks }) + ';',
    'window.TURN_LABEL_PRESETS = ' + JSON.stringify(presets) + ';',
    '',
  ].join('\n');
  return {
    text,
    tracks: Object.keys(tracks),
    presetSlugs: Object.keys(presets),
    skipped,
    count,
    bytes: Buffer.byteLength(text),
  };
}

function main(argv) {
  const args = argv.slice(2);
  const outIndex = args.indexOf('--out');
  const target = outIndex >= 0 ? path.resolve(args[outIndex + 1]) : TARGET;
  const built = render();
  const lines = built.text.split('\n').length - 1;

  if (args.includes('--check')) {
    const current = fs.existsSync(target) ? fs.readFileSync(target, 'utf8') : '';
    if (current !== built.text) {
      console.error(`STALE ${path.relative(ROOT, target)} — run: node dev/scripts/build_turn_label_editor.js`);
      return 1;
    }
    console.log(`ok ${path.relative(ROOT, target)}: ${built.tracks.length} tracks, ` +
      `${built.presetSlugs.length} preset(s)`);
    return 0;
  }

  fs.writeFileSync(target, built.text);
  console.log(`wrote ${path.relative(ROOT, target)} — ${built.tracks.length} track(s) with baked turns of ` +
    `${built.count} outline file(s)${built.skipped.length ? ` (${built.skipped.length} have no turns)` : ''}, ` +
    `${built.presetSlugs.length} preset(s) (${built.presetSlugs.join(', ') || 'none'}), ` +
    `${(built.bytes / 1024).toFixed(0)} KB, ${lines} lines`);
  if (lines > CEILING) {
    console.error(`FAIL: ${lines} lines exceeds the ${CEILING}-line ceiling`);
    return 1;
  }
  return 0;
}

if (require.main === module) process.exit(main(process.argv));
module.exports = { render, buildPayload };
