// SLICE-01 SPIKE v2 (throwaway) — turn labels that stay ON their corner.
//
// Rules from the review of v1:
//   - type ~30% smaller than the 8.25 px v1 default  -> 5.75 px at 250 px
//   - a label must stay ADJACENT to its corner: displacement is capped, and
//     sliding along the track is preferred over pushing away from it
//   - strings must never overlap each other (hard rule)
//   - crossing the track ribbon is fine (no ribbon-clearance constraint)
//   - degrade the text before moving a label: "T2 Roggia 2" -> "T2"
//
// Usage: node render_labels.mjs [slug ...]
// Writes labels-<slug>-<tag>.png + placement-report.json next to this file.
// Nothing here is production code.

import { chromium } from 'playwright';
import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
let ROOT = HERE;
while (!existsSync(path.join(ROOT, 'product/data'))) ROOT = path.dirname(ROOT);

const MAP_PAD = 20;        // pipeline.js PAD
const FONT_RATIO = 0.023;  // 5.75 px at 250 px (v1 used 0.033 = 8.25 px)
const FONT_MIN = 5;
const FONT_MAX = 8;
const GAP_RATIO = 0.75;    // gap_px = fontSize * GAP_RATIO
// Adjacency budget, in multiples of the font size. A label may be nudged at
// most this far from its raw position, and along-track nudges are tried first.
const BUDGET = [0, 1.2, -1.2, 2.4, -2.4];

function buildTransform(bbox, mapSize) {
  const inner = mapSize - 2 * MAP_PAD;
  const width = bbox.maxX - bbox.minX || 1;
  const height = bbox.maxY - bbox.minY || 1;
  const scale = Math.min(inner / width, inner / height);
  const offsetX = MAP_PAD + (inner - width * scale) / 2;
  const offsetZ = MAP_PAD + (inner - height * scale) / 2;
  return {
    scale,
    toMapX: x => offsetX + (x - bbox.minX) * scale,
    toMapZ: y => offsetZ + (bbox.maxY - y) * scale,
  };
}

function fontSizeFor(mapSize, ratio, floor) {
  const raw = mapSize * ratio;
  return floor ? Math.max(FONT_MIN, Math.min(FONT_MAX, raw)) : raw;
}

// Text variants, best first: full short name, then number only.
function textVariants(turn) {
  const name = turn.short || turn.name;
  const out = [];
  if (name) out.push(`T${turn.number} ${name}`);
  out.push(`T${turn.number}`);
  return [...new Set(out)];
}

function buildSvg(outline, anchors, cfg) {
  const { size, ratio, floor } = cfg;
  const tf = buildTransform(anchors.bbox, size);
  const fontSize = fontSizeFor(size, ratio, floor);
  const gapPx = fontSize * GAP_RATIO;
  const poly = pts => pts
    .map(p => `${tf.toMapX(p.x).toFixed(1)},${tf.toMapZ(p.y).toFixed(1)}`)
    .join(' ');

  // Every possible (text, nudge) pair is pre-rendered as a hidden element; the
  // resolve pass reveals the first one that does not collide. Keeps the DOM
  // measurable without re-laying out the whole map per attempt.
  const candidates = [];
  anchors.turns.forEach((turn, i) => {
    const nx = turn.outward[0];
    const ny = -turn.outward[1];             // screen space (toMapZ inverts Y)
    const tx = turn.tangent[0];
    const ty = -turn.tangent[1];
    const ax = tf.toMapX(turn.x);
    const ay = tf.toMapZ(turn.y);
    const anchor = nx > 0.35 ? 'start' : nx < -0.35 ? 'end' : 'middle';
    const baseline = ny > 0.35 ? 'hanging' : ny < -0.35 ? 'auto' : 'middle';
    textVariants(turn).forEach((text, tIdx) => {
      BUDGET.forEach((step, sIdx) => {
        // Alternate along-track and outward nudges; index 0 is the raw spot.
        const along = sIdx % 2 === 1;
        const dx = along ? tx * step * fontSize : nx * step * fontSize;
        const dy = along ? ty * step * fontSize : ny * step * fontSize;
        const x = ax + nx * gapPx + dx;
        const y = ay + ny * gapPx + dy;
        candidates.push({
          turn: i, number: turn.number, text, tIdx, sIdx,
          x, y, anchor, baseline,
          ax, ay,
          displacement: Math.hypot(x - (ax + nx * gapPx), y - (ay + ny * gapPx)),
        });
      });
    });
  });

  const candidateSvg = candidates.map((c, i) => [
    `<text class="turn-label" data-c="${i}" data-turn="${c.turn}" data-t="${c.tIdx}" data-s="${c.sIdx}"`,
    ` x="${c.x.toFixed(2)}" y="${c.y.toFixed(2)}" font-size="${fontSize.toFixed(2)}"`,
    ` text-anchor="${c.anchor}" dominant-baseline="${c.baseline}" style="visibility:hidden">`,
    `${c.text.replace(/&/g, '&amp;').replace(/</g, '&lt;')}</text>`,
  ].join('')).join('\n');

  return `<svg id="map" xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"
      viewBox="0 0 ${size} ${size}">
  <style>
    #map { background: #14161a; }
    .bnd { fill: none; stroke: #8a919c; stroke-width: .9; stroke-linejoin: round; }
    .ctr { fill: none; stroke: #8a919c; stroke-width: .6; stroke-dasharray: 2 3; opacity: .55; }
    .tick { stroke: #555f6b; stroke-width: .4; stroke-dasharray: 1 1.5; }
    .turn-label { fill: #f3f5f8; font-family: Inter, Segoe UI, Arial, sans-serif;
                  font-weight: 600; letter-spacing: -.1px; }
    .apex { fill: #f0a020; }
  </style>
  <polyline class="bnd" points="${poly(outline.left_boundary)}"/>
  <polyline class="bnd" points="${poly(outline.right_boundary)}"/>
  <polyline class="ctr" points="${poly(outline.centerline)}"/>
  <g id="apexes">${anchors.turns.map(t => {
    const cx = tf.toMapX(t.x).toFixed(1), cy = tf.toMapZ(t.y).toFixed(1);
    return `<circle class="apex" cx="${cx}" cy="${cy}" r="0.8"/>`;
  }).join('')}</g>
  <g id="ticks"></g>
${candidateSvg}
</svg>`;
}

// Page-side resolve: first non-overlapping candidate per turn (in turn order),
// preferring the raw position and the fullest text. Returns the placement.
function resolve({ mapSize, margin, gapPx, fontSize }) {
  const svg = document.getElementById('map');
  const svgRect = svg.getBoundingClientRect();
  const rectOf = el => {
    const b = el.getBoundingClientRect();
    return { x: b.x - svgRect.x, y: b.y - svgRect.y, w: b.width, h: b.height };
  };
  const clash = (a, b) => {
    const x = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
    const y = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
    return x > 0 && y > 0;
  };
  const all = [...document.querySelectorAll('.turn-label')];
  const byTurn = new Map();
  for (const el of all) {
    const t = Number(el.dataset.turn);
    if (!byTurn.has(t)) byTurn.set(t, []);
    byTurn.get(t).push(el);
  }
  // Sort candidates per turn: full text first, then smallest displacement.
  for (const list of byTurn.values()) {
    list.sort((a, b) => Number(a.dataset.t) - Number(b.dataset.t) ||
                        Number(a.dataset.s) - Number(b.dataset.s));
  }

  const apexes = [...document.querySelectorAll('.apex')].map(c => ({
    x: Number(c.getAttribute('cx')), y: Number(c.getAttribute('cy')),
  }));
  const placed = [];
  const ticks = document.getElementById('ticks');
  const result = [];
  for (const [turn, list] of [...byTurn.entries()].sort((a, b) => a[0] - b[0])) {
    let chosen = null, rect = null;
    for (const el of list) {
      const r = rectOf(el);
      const inside = r.x >= margin && r.y >= margin &&
                     r.x + r.w <= mapSize - margin && r.y + r.h <= mapSize - margin;
      if (!inside) continue;
      if (placed.some(k => clash(r, k))) continue;
      chosen = el; rect = r; break;
    }
    if (!chosen) {
      result.push({ turn, text: null, dropped: true });
      continue;
    }
    chosen.style.visibility = 'visible';
    placed.push(rect);
    const apex = apexes[turn];
    ticks.insertAdjacentHTML('beforeend',
      `<line class="tick" x1="${apex.x.toFixed(1)}" y1="${apex.y.toFixed(1)}"` +
      ` x2="${(rect.x + rect.w / 2).toFixed(1)}" y2="${(rect.y + rect.h / 2).toFixed(1)}"/>`);
    result.push({
      turn,
      text: chosen.textContent,
      degradedToNumber: Number(chosen.dataset.t) > 0,
      nudgeIndex: Number(chosen.dataset.s),
      x: Number(rect.x.toFixed(1)), y: Number(rect.y.toFixed(1)),
      w: Number(rect.w.toFixed(1)), h: Number(rect.h.toFixed(1)),
    });
  }

  // Overlap audit on what is actually visible (must be 0).
  const visible = result.filter(r => !r.dropped)
    .map(r => ({ text: r.text, x: r.x, y: r.y, w: r.w, h: r.h }));
  const overlaps = [];
  for (let i = 0; i < visible.length; i++) {
    for (let j = i + 1; j < visible.length; j++) {
      if (clash(visible[i], visible[j])) overlaps.push([visible[i].text, visible[j].text]);
    }
  }
  // Distance of each label centre to its own apex marker, in px.
  for (const r of result) {
    if (r.dropped) continue;
    const a = apexes[r.turn];
    r.apexToLabelCentrePx = Number(Math.hypot(
      (r.x + r.w / 2) - a.x, (r.y + r.h / 2) - a.y).toFixed(1));
    // Distance from the apex to the label RECT (0 when the apex is under the text):
    // the honest "is this adjacent?" number.
    const dx = Math.max(r.x - a.x, 0, a.x - (r.x + r.w));
    const dy = Math.max(r.y - a.y, 0, a.y - (r.y + r.h));
    r.apexToRectPx = Number(Math.hypot(dx, dy).toFixed(1));
  }
  return { result, overlaps, fontSize, gapPx, mapSize };
}

const CONFIGS = [
  { size: 250, ratio: FONT_RATIO, floor: true, tag: '250' },
  { size: 120, ratio: FONT_RATIO, floor: true, tag: '120' },
  { size: 120, ratio: FONT_RATIO, floor: false, tag: '120-nofloor' },
];

const slugs = process.argv.slice(2).length
  ? process.argv.slice(2)
  : ['silverstone-international-circuit', 'monza-curva-grande-circuit'];

const browser = await chromium.launch();
const ctx = await browser.newContext({ deviceScaleFactor: 3 });
const report = {};

for (const slug of slugs) {
  const outline = JSON.parse(await readFile(
    path.join(ROOT, 'product/data/track-outlines', `${slug}.json`), 'utf8'));
  const anchors = JSON.parse(await readFile(path.join(HERE, `anchors-${slug}.json`), 'utf8'));
  report[slug] = { turns: anchors.turns.length, configs: {} };
  console.log(`\n${slug} (${anchors.turns.length} turns)`);
  const page = await ctx.newPage();
  for (const cfg of CONFIGS) {
    const fontSize = fontSizeFor(cfg.size, cfg.ratio, cfg.floor);
    await page.setContent(`<body style="margin:0;background:#14161a">${buildSvg(outline, anchors, cfg)}</body>`);
    const res = await page.evaluate(resolve, {
      mapSize: cfg.size, margin: 1, gapPx: fontSize * GAP_RATIO, fontSize,
    });
    const shown = res.result.filter(r => !r.dropped);
    const dists = shown.map(r => r.apexToLabelCentrePx);
    const entry = {
      sizePx: cfg.size, fontPx: Number(fontSize.toFixed(2)), floor: cfg.floor,
      shown: shown.length, dropped: res.result.filter(r => r.dropped).map(r => `T${r.turn + 1}`),
      overlaps: res.overlaps,
      degradedToNumber: shown.filter(r => r.degradedToNumber).map(r => r.text),
      maxApexToLabelCentrePx: Number(Math.max(...dists).toFixed(1)),
      meanApexToRectPx: Number((shown.reduce((s, r) => s + r.apexToRectPx, 0) / shown.length).toFixed(1)),
      maxApexToRectPx: Number(Math.max(...shown.map(r => r.apexToRectPx)).toFixed(1)),
      minLabelPairGapPx: (() => {
        let best = Infinity;
        for (let i = 0; i < shown.length; i++) {
          for (let j = i + 1; j < shown.length; j++) {
            const a = shown[i], b = shown[j];
            const gx = Math.max(a.x - (b.x + b.w), b.x - (a.x + a.w), 0);
            const gy = Math.max(a.y - (b.y + b.h), b.y - (a.y + a.h), 0);
            best = Math.min(best, Math.hypot(gx, gy));
          }
        }
        return Number(best.toFixed(1));
      })(),
      meanApexToLabelCentrePx: Number((dists.reduce((s, d) => s + d, 0) / dists.length).toFixed(1)),
      labels: shown.map(r => ({ text: r.text, nudge: r.nudgeIndex,
                                distCentre: r.apexToLabelCentrePx, distRect: r.apexToRectPx })),
    };
    report[slug].configs[cfg.tag] = entry;
    await page.setViewportSize({ width: cfg.size, height: cfg.size });
    await page.locator('#map').screenshot({ path: path.join(HERE, `labels-${slug}-${cfg.tag}.png`) });
    console.log(`  ${cfg.tag.padEnd(11)} font=${entry.fontPx}px shown=${entry.shown}/${anchors.turns.length}` +
      ` overlaps=${entry.overlaps.length} dropped=${entry.dropped.join(',') || '-'}` +
      ` numbers-only=${entry.degradedToNumber.join(',') || '-'}`);
    console.log(`              apex->label box: mean ${entry.meanApexToRectPx}px max ${entry.maxApexToRectPx}px` +
      ` | min gap between labels ${entry.minLabelPairGapPx}px`);
  }
  await page.close();
}

await browser.close();
await writeFile(path.join(HERE, 'placement-report.json'), JSON.stringify(report, null, 2) + '\n');
console.log('\nwrote placement-report.json + PNGs');
