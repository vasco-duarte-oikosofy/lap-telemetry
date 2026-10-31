#!/usr/bin/env node
'use strict';

/**
 * Unit tests for the turn-label layout algorithm (docs/specs/MAP_TURN_NAMES.md).
 *
 * The planner is pure: text metrics are injected, so the whole placement rule —
 * alternating sides, text tiers, adjacency caps, no-overlap resolution — is
 * testable without a browser.
 */

const path = require('path');
const { pathToFileURL } = require('url');
const ROOT = path.resolve(__dirname, '../..');

let pass = 0;
let fail = 0;

function check(name, fn) {
  try {
    fn();
    console.log(`  [PASS] ${name}`);
    pass += 1;
  } catch (err) {
    console.log(`  [FAIL] ${name} — ${err.message}`);
    fail += 1;
  }
}

const assert = (cond, msg) => { if (!cond) throw new Error(msg); };

// Fake metrics: 0.55 em per character, 1.15 em tall — deterministic, and close
// enough to real SVG metrics for the rules under test.
const measure = (text, fontSize) => ({ w: text.length * 0.55 * fontSize, h: 1.15 * fontSize });

// Mimics pipeline.js buildTrackTransform, which inverts the world Y axis.
const identity = { toMapX: x => x, toMapZ: z => 250 - z };

// Straight-line fake track inside the map: apexes `step` apart along +x on the
// y = 125 centre line, every normal +y (so "outside" is +y).
function fakeTurns(n, { step = 60, x0 = 40, name = i => `Corner ${i + 1}`, shortName = () => null } = {}) {
  return Array.from({ length: n }, (_, i) => ({
    number: i + 1,
    name: name(i),
    short_name: shortName(i),
    apex_s_m: 100 + i * step,
    x: x0 + i * step,
    y: 125,
    outward: [0, 1],
    tangent: [1, 0],
  }));
}

const overlaps = (a, b) => {
  const x = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const y = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return x > 0 && y > 0;
};

function runAll({ planTurnLabels, fontSizeFor, turnLabelTexts, TURN_LABEL_CONFIG }) {
  const plan = (turns, mapSize) =>
    planTurnLabels({ turns, ...identity, mapSize, measure });

  // Same, for maps whose size is not 250 (the fixture inverts about 250).
  const planAt = (turns, mapSize) =>
    planTurnLabels({ turns, toMapX: x => x, toMapZ: z => mapSize - z, mapSize, measure });

  check('small maps keep the reviewed 5.75 px / 5 px sizes', () => {
    assert(Math.abs(fontSizeFor(250) - 5.75) < 1e-9, `250 px -> ${fontSizeFor(250)}`);
    assert(Math.abs(fontSizeFor(120) - 5) < 1e-9, `120 px -> ${fontSizeFor(120)}`);
  });

  // The compare app's map panel is 500-950 px wide, so the type must grow with
  // it. A hard 8 px ceiling (the 250 px spike's value) left 8 px text on a
  // 910 px map, which is what "the font is too small in compare.html" was.
  check('type grows with the map instead of stopping at the 250 px size', () => {
    assert(Math.abs(fontSizeFor(574) - 13.2) < 0.05, `574 px -> ${fontSizeFor(574)}`);
    assert(Math.abs(fontSizeFor(622) - 14.31) < 0.05, `622 px -> ${fontSizeFor(622)}`);
    assert(Math.abs(fontSizeFor(574) / 574 - TURN_LABEL_CONFIG.fontRatio) < 1e-9, 'ratio not applied');
    assert(fontSizeFor(574) > 8, 'product map still clamped to 8 px');
    assert(fontSizeFor(650) > fontSizeFor(500), 'not monotonic');
    assert(Math.abs(fontSizeFor(1500) - TURN_LABEL_CONFIG.fontMax) < 1e-9, 'ceiling not applied');
  });

  check('every turn gets a label when there is room', () => {
    const res = plan(fakeTurns(4), 250);
    assert(res.labels.length === 4, `placed ${res.labels.length}`);
    assert(res.dropped.length === 0, `dropped ${res.dropped.length}`);
    assert(res.labels[0].text === 'T1 Corner 1', `text ${res.labels[0].text}`);
  });

  check('sides alternate: odd turns outside, even turns inside', () => {
    const turns = fakeTurns(4);
    const res = plan(turns, 250);
    const sides = res.labels.map(l => l.side);
    assert(JSON.stringify(sides) === JSON.stringify([1, -1, 1, -1]), `sides ${sides}`);
    // toMapZ inverts Y, so a world +y outward normal puts the outside label
    // ABOVE its apex on screen (smaller y).
    assert(res.labels[0].y < 125, `T1 (outside) y ${res.labels[0].y.toFixed(1)} should be above 125`);
    assert(res.labels[1].y > 125, `T2 (inside) y ${res.labels[1].y.toFixed(1)} should be below 125`);
  });

  check('labels never overlap each other', () => {
    const res = plan(fakeTurns(12), 250);
    for (let i = 0; i < res.labels.length; i++) {
      for (let j = i + 1; j < res.labels.length; j++) {
        assert(!overlaps(res.labels[i], res.labels[j]),
          `${res.labels[i].text} overlaps ${res.labels[j].text}`);
      }
    }
  });

  check('labels stay adjacent: normal offset capped by map size, along-track by font', () => {
    const turns = fakeTurns(12);
    const res = plan(turns, 250);
    const fontSize = fontSizeFor(250);
    const normalCap = Math.min(2.4 * fontSize, 0.04 * 250);
    const alongCap = 2.4 * fontSize;
    for (const l of res.labels) {
      const apex = turns[l.turn];
      const normalOffset = Math.abs((l.y + l.h / 2) - apex.y);
      const alongOffset = Math.abs((l.x + l.w / 2) - apex.x);
      assert(normalOffset <= normalCap + l.h / 2 + 1e-6,
        `${l.text} normal offset ${normalOffset.toFixed(1)} > ${normalCap.toFixed(1)} + half height`);
      assert(alongOffset <= alongCap + l.w / 2 + 1e-6,
        `${l.text} along offset ${alongOffset.toFixed(1)} > ${alongCap.toFixed(1)} + half width`);
    }
  });

  check('all labels stay inside the viewBox', () => {
    const res = plan(fakeTurns(6), 250);
    for (const l of res.labels) {
      assert(l.x >= 0 && l.y >= 0 && l.x + l.w <= 250 && l.y + l.h <= 250,
        `${l.text} outside viewBox: ${JSON.stringify({ x: +l.x.toFixed(1), y: +l.y.toFixed(1) })}`);
    }
  });

  check('a crowded map degrades text to T<n> before dropping a label', () => {
    const turns = fakeTurns(40, { step: 5, name: i => `Very Long Corner Name ${i + 1}` });
    const res = plan(turns, 250);
    assert(res.labels.some(l => /^T\d+$/.test(l.text)), 'expected some labels to fall back to T<n>');
    assert(res.labels.length + res.dropped.length === turns.length, 'a turn vanished silently');
  });

  check('unnamed corners render as T<n> only', () => {
    const turns = fakeTurns(2, { name: () => null });
    const res = plan(turns, 250);
    assert(res.labels.every(l => /^T\d+$/.test(l.text)), `texts ${res.labels.map(l => l.text)}`);
  });

  check('short_name wins over name', () => {
    const turns = fakeTurns(1, {
      name: () => 'Curva Alboreto (Parabolica)',
      shortName: () => 'Parabolica',
    });
    const res = plan(turns, 250);
    assert(res.labels[0].text === 'T1 Parabolica', `text ${res.labels[0].text}`);
  });

  check('text tiers: "<n> <name>" is only offered below 150 px', () => {
    const turn = { number: 4, name: 'Laranjinha', short_name: null };
    const small = turnLabelTexts(turn, 120);
    const large = turnLabelTexts(turn, 250);
    assert(small.includes('4 Laranjinha'), `120 px variants ${small}`);
    assert(!large.includes('4 Laranjinha'), `250 px variants ${large}`);
    assert(small[0] === 'T4 Laranjinha' && small[small.length - 1] === 'T4',
      `order must be best-first: ${small}`);
  });

  check('deterministic: same input, same placement', () => {
    const a = plan(fakeTurns(9), 250);
    const b = plan(fakeTurns(9), 250);
    assert(JSON.stringify(a) === JSON.stringify(b), 'planner is not deterministic');
  });

  check('empty turn list plans nothing', () => {
    const res = plan([], 250);
    assert(res.labels.length === 0 && res.dropped.length === 0, 'expected no labels');
  });
}

(async () => {
  // product/ modules are ESM; on Windows a bare path fails the ESM loader.
  const mod = await import(pathToFileURL(path.join(ROOT, 'product/web/js/turnLabels.js')).href);
  runAll(mod);
  console.log(`\n${pass}/${pass + fail} assertions passed`);
  if (fail > 0) {
    console.log('RESULT: FAIL');
    process.exit(1);
  }
  console.log('RESULT: PASS');
})();
