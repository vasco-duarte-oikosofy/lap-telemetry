// SLICE-01 SPIKE (throwaway) — render turn labels over the track outline,
// measure their real bounding boxes, and score placement quality.
//
// Usage: node render_labels.mjs [slug ...]
//
// Writes labels-<slug>-<tag>.png next to this file and prints, per config:
//   overlaps  — label rect pairs that intersect (the declutter budget)
//   clipped   — labels that leave the map viewBox
//   clearance — min distance (px) from a label rect to the track centreline
//   dropped   — labels suppressed by the greedy declutter pass
//
// Nothing here is production code; constants are here to be tuned and measured.

import { chromium } from 'playwright';
import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
let ROOT = HERE;
while (!existsSync(path.join(ROOT, 'product/data'))) ROOT = path.dirname(ROOT);

const MAP_PAD = 20;       // pipeline.js PAD
const FONT_MIN = 6;
const FONT_MAX = 11;
const GAP_RATIO = 0.9;    // gap_px = fontSize * GAP_RATIO
const CHAIN_GAP_M = 150;  // corners closer than this share a chain (chicanes)
const STAGGER_STEP = 1.45; // extra gap multiples per chain member

// Same math as pipeline.js buildTrackTransform, parameterised by map size.
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

// Chained sub-turns (chicane / complex apices) sit tens of metres apart, so
// their labels collide head-on. Give each chain member a longer gap (1x, 2.45x,
// 3.9x, ...) so the labels stack outwards instead of overlapping.
function staggerMultipliers(turns) {
  const mult = [];
  let run = 0;
  turns.forEach((t, i) => {
    if (i > 0 && t.apex_s_m - turns[i - 1].apex_s_m < CHAIN_GAP_M) run += 1;
    else run = 0;
    mult.push(1 + STAGGER_STEP * run);
  });
  return mult;
}

function labelText(turn, mode) {
  if (mode === 'numbers') return `T${turn.number}`;
  const name = mode === 'short' ? (turn.short || turn.name) : turn.name;
  return name ? `T${turn.number} ${name}` : `T${turn.number}`;
}

function buildSvg(outline, anchors, cfg) {
  const { size, ratio, floor } = cfg;
  const tf = buildTransform(anchors.bbox, size);
  const fontSize = fontSizeFor(size, ratio, floor);
  const gapPx = fontSize * GAP_RATIO;
  const stagger = cfg.stagger ? staggerMultipliers(anchors.turns) : anchors.turns.map(() => 1);
  const poly = pts => pts
    .map(p => `${tf.toMapX(p.x).toFixed(1)},${tf.toMapZ(p.y).toFixed(1)}`)
    .join(' ');

  const labels = anchors.turns.map((turn, i) => {
    const nx = turn.outward[0];
    const ny = -turn.outward[1]; // screen space: toMapZ inverts world Y
    const gapWorld = (gapPx * stagger[i]) / tf.scale;
    return {
      turn,
      ax: tf.toMapX(turn.x),
      ay: tf.toMapZ(turn.y),
      x: tf.toMapX(turn.x + nx * gapWorld),
      y: tf.toMapZ(turn.y + ny * gapWorld),
      anchor: nx > 0.35 ? 'start' : nx < -0.35 ? 'end' : 'middle',
      baseline: ny > 0.35 ? 'hanging' : ny < -0.35 ? 'auto' : 'middle',
      nx, ny, gapPx,
    };
  });

  const labelSvg = labels.map(({ turn, ax, ay, x, y, anchor, baseline, nx, ny, gapPx }) => [
    `<line class="tick" x1="${ax.toFixed(1)}" y1="${ay.toFixed(1)}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"/>`,
    `<text class="turn-label" data-n="${turn.number}" data-nx="${nx.toFixed(3)}" data-ny="${(-ny).toFixed(3)}"` +
    ` data-ax="${ax.toFixed(1)}" data-ay="${ay.toFixed(1)}" data-gap="${gapPx.toFixed(2)}"` +
    ` x="${x.toFixed(1)}" y="${y.toFixed(1)}"`,
    ` font-size="${fontSize.toFixed(2)}" text-anchor="${anchor}" dominant-baseline="${baseline}">`,
    `${labelText(turn, cfg.names).replace(/&/g, '&amp;').replace(/</g, '&lt;')}</text>`,
  ].join('')).join('\n');

  return `<svg id="map" xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"
      viewBox="0 0 ${size} ${size}">
  <style>
    #map { background: #14161a; }
    .bnd { fill: none; stroke: #8a919c; stroke-width: .9; stroke-linejoin: round; }
    .ctr { fill: none; stroke: #8a919c; stroke-width: .6; stroke-dasharray: 2 3; opacity: .55; }
    .tick { stroke: #4b5563; stroke-width: .5; stroke-dasharray: 1 1.5; }
    .turn-label { fill: #f3f5f8; font-family: Inter, Segoe UI, Arial, sans-serif;
                  font-weight: 600; letter-spacing: -.2px; }
  </style>
  <polyline id="bnd-l" class="bnd" points="${poly(outline.left_boundary)}"/>
  <polyline id="bnd-r" class="bnd" points="${poly(outline.right_boundary)}"/>
  <polyline id="ctr" class="ctr" points="${poly(outline.centerline)}"/>
${labelSvg}
</svg>`;
}

// Runs in the page. Placement pass:
//   1. push each label outward along its normal until it clears (a) already
//      placed labels and (b) the track ribbon, or the push budget runs out;
//   2. clamp the result into the viewBox (labels may not be clipped);
//   3. drop only what still clashes after both � last resort, reported.
function resolveLabels({ mapSize, push, clamp, drop, margin, clearPx, maxPushPx, stepPx }) {
  const svg = document.getElementById('map');
  const svgRect = svg.getBoundingClientRect();
  const rectOf = el => {
    const b = el.getBoundingClientRect();
    return { x: b.x - svgRect.x, y: b.y - svgRect.y, w: b.width, h: b.height };
  };
  const texts = [...document.querySelectorAll('.turn-label')];
  const ticks = [...document.querySelectorAll('.tick')];

  const segDist = (px, py, ax, ay, bx, by) => {
    const dx = bx - ax, dy = by - ay;
    const len2 = dx * dx + dy * dy;
    let t = len2 ? ((px - ax) * dx + (py - ay) * dy) / len2 : 0;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
  };
  const ribbonPts = ['bnd-l', 'bnd-r'].flatMap(id =>
    (document.getElementById(id).getAttribute('points') || '').trim().split(/\s+/)
      .map(pair => { const [x, y] = pair.split(',').map(Number); return { x, y }; }));
  const ctrPts = (document.getElementById('ctr').getAttribute('points') || '').trim()
    .split(/\s+/).map(pair => { const [x, y] = pair.split(',').map(Number); return { x, y }; });

  const minDistTo = (rect, pts) => {
    const samples = [[rect.x, rect.y], [rect.x + rect.w, rect.y], [rect.x, rect.y + rect.h],
                     [rect.x + rect.w, rect.y + rect.h], [rect.x + rect.w / 2, rect.y + rect.h / 2]];
    let best = Infinity;
    for (const [sx, sy] of samples) {
      for (let i = 1; i < pts.length; i++) {
        const d = segDist(sx, sy, pts[i - 1].x, pts[i - 1].y, pts[i].x, pts[i].y);
        if (d < best) best = d;
      }
    }
    return best;
  };
  const clash = (a, b) => {
    const x = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
    const y = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
    return x > 0 && y > 0;
  };

  const placed = [];
  const dropped = [];
  texts.forEach((el, i) => {
    const nx = Number(el.dataset.nx);
    const ny = Number(el.dataset.ny);         // already screen-space
    const ax = Number(el.dataset.ax);
    const ay = Number(el.dataset.ay);
    const baseGap = Number(el.dataset.gap);
    let gap = baseGap;
    let rect = null;
    for (let attempt = 0; attempt < 10; attempt++) {
      const x = ax + nx * gap;
      const y = ay + ny * gap;
      el.setAttribute('x', x.toFixed(2));
      el.setAttribute('y', y.toFixed(2));
      if (ticks[i]) {
        ticks[i].setAttribute('x2', x.toFixed(2));
        ticks[i].setAttribute('y2', y.toFixed(2));
      }
      rect = rectOf(el);
      const ribbonClear = minDistTo(rect, ribbonPts);
      const labelClash = placed.some(k => clash(rect, k));
      const outside = rect.x < 0 || rect.y < 0 ||
                      rect.x + rect.w > mapSize || rect.y + rect.h > mapSize;
      if (!labelClash && ribbonClear >= clearPx && !outside) break;
      if (!push || gap > baseGap + maxPushPx) { break; }
      gap += stepPx;
    }
    if (clamp) {
      let dx = 0, dy = 0;
      if (rect.x < margin) dx = margin - rect.x;
      if (rect.x + rect.w > mapSize - margin) dx = mapSize - margin - (rect.x + rect.w);
      if (rect.y < margin) dy = margin - rect.y;
      if (rect.y + rect.h > mapSize - margin) dy = mapSize - margin - (rect.y + rect.h);
      if (dx || dy) {
        el.setAttribute('transform', `translate(${dx.toFixed(2)},${dy.toFixed(2)})`);
        rect = rectOf(el);
      }
    }
    if (drop && placed.some(k => clash(rect, k))) {
      dropped.push(el.textContent);
      el.style.display = 'none';
      if (ticks[i]) ticks[i].style.display = 'none';
      return;
    }
    placed.push(rect);
    el.dataset.finalClear = minDistTo(rect, ribbonPts).toFixed(2);
  });

  const boxes = texts.filter(el => el.style.display !== 'none').map(el => {
    const b = rectOf(el);
    return {
      text: el.textContent, x: b.x, y: b.y, w: b.w, h: b.h,
      clearance: Number(Math.min(minDistTo(b, ribbonPts), minDistTo(b, ctrPts)).toFixed(2)),
      clipped: b.x < 0 || b.y < 0 || b.x + b.w > mapSize || b.y + b.h > mapSize,
    };
  });
  return { boxes, dropped };
}

function overlapPairs(boxes) {
  const hits = [];
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      const x = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
      const y = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
      if (x > 0 && y > 0) hits.push({ a: a.text, b: b.text, area: Math.round(x * y) });
    }
  }
  return hits;
}

const CONFIGS = [
  // raw placement, nothing resolved: shows the real overlap/clipping cost
  { size: 250, ratio: 0.033, floor: true, tag: '00-250-raw-official' },
  { size: 250, ratio: 0.033, floor: true, names: 'short', tag: '00b-250-raw-short' },
  // resolved: push outward along the normal, clamp into the viewBox, then drop
  { size: 250, ratio: 0.033, floor: true, names: 'official', push: true, clamp: true, drop: true, tag: '02-250-push-official' },
  { size: 250, ratio: 0.033, floor: true, names: 'short', push: true, clamp: true, drop: true, tag: '08-250-push-short' },
  { size: 250, ratio: 0.033, floor: true, names: 'numbers', push: true, clamp: true, drop: true, tag: '10-250-numbers' },
  // TinyPedal-sized map (area_size floor is 100 px there)
  { size: 120, ratio: 0.033, floor: true, names: 'short', push: true, clamp: true, drop: true, tag: '09-120-push-short' },
  { size: 120, ratio: 0.033, floor: true, names: 'numbers', push: true, clamp: true, drop: true, tag: '11-120-numbers' },
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
  report[slug] = { gapWorld: anchors.gap_world, turns: anchors.turns.length, configs: {} };
  console.log(`\n${slug}  (${anchors.turns.length} turns, gap ${anchors.gap_world} world units @250)`);

  const page = await ctx.newPage();
  for (const cfg of CONFIGS) {
    await page.setContent(`<body style="margin:0;background:#14161a">${buildSvg(outline, anchors, cfg)}</body>`);
    const { boxes, dropped } = await page.evaluate(resolveLabels, {
      mapSize: cfg.size, push: Boolean(cfg.push), clamp: Boolean(cfg.clamp), drop: Boolean(cfg.drop),
      margin: 1, clearPx: 2, maxPushPx: 26, stepPx: 2,
      // stagger is now expressed as a starting gap, not a multiplier
    });
    const hits = overlapPairs(boxes);
    const widths = boxes.map(b => b.w);
    const entry = {
      sizePx: cfg.size, fontRatio: cfg.ratio, floor: cfg.floor, short: cfg.names === 'short', names: cfg.names || 'official',
      clamp: Boolean(cfg.clamp), push: Boolean(cfg.push),
      fontPx: Number(fontSizeFor(cfg.size, cfg.ratio, cfg.floor).toFixed(2)),
      labels: boxes.length, dropped, overlaps: hits.length, overlapPairs: hits,
      clipped: boxes.filter(b => b.clipped).map(b => b.text),
      minClearancePx: Number(Math.min(...boxes.map(b => b.clearance)).toFixed(2)),
      widestLabelPx: Number(Math.max(...widths).toFixed(1)),
      meanLabelPx: Number((widths.reduce((s, w) => s + w, 0) / widths.length).toFixed(1)),
      labelsDetail: boxes.map(b => ({ text: b.text, w: Number(b.w.toFixed(1)),
                                      clearance: b.clearance, clipped: b.clipped })),
    };
    report[slug].configs[cfg.tag] = entry;
    await page.setViewportSize({ width: cfg.size, height: cfg.size });
    await page.locator('#map').screenshot({ path: path.join(HERE, `labels-${slug}-${cfg.tag}.png`) });
    console.log(`  ${cfg.tag.padEnd(26)} font=${String(entry.fontPx).padEnd(5)} shown=${String(entry.labels).padEnd(2)}` +
      ` dropped=${entry.dropped.length} overlaps=${entry.overlaps}` +
      ` clear>=${String(entry.minClearancePx).padEnd(5)} widest=${entry.widestLabelPx}px mean=${entry.meanLabelPx}px` +
      `${entry.clipped.length ? ` CLIPPED=${entry.clipped.length}` : ''}`);
    hits.forEach(h => console.log(`      overlap "${h.a}" x "${h.b}" (${h.area} px2)`));
    if (dropped.length) console.log(`      dropped: ${dropped.join(' | ')}`);
  }
  await page.close();
}

await browser.close();
await writeFile(path.join(HERE, 'overlap-report.json'), JSON.stringify(report, null, 2) + '\n');
console.log('\nwrote overlap-report.json + PNGs');
