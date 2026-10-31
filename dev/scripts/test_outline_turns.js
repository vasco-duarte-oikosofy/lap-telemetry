#!/usr/bin/env node
'use strict';

/**
 * Guard tests for the curated `turns` block in track outlines
 * (docs/specs/MAP_TURN_NAMES.md).
 *
 * 1. `withPreservedTurns` carries curated turns across outline regeneration.
 * 2. Every outline writer wires that helper — a writer that forgets it would
 *    silently delete every curated turn name (bug-24 discipline).
 * 3. Baked `turns` blocks are well-formed: unique 1-based numbers, finite
 *    anchors inside the outline bbox, unit normal/tangent vectors, names that
 *    are never the generator's placeholders.
 * 4. The static ES module carries the same turns as the source JSON.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const assert = require('assert');

const ROOT = path.resolve(__dirname, '../..');
const OUTLINES_DIR = path.join(ROOT, 'product/data/track-outlines');
const MODELS_DIR = path.join(ROOT, 'product/data/track-coaching');
const { withPreservedTurns, readExistingTurns } = require('./lib/outlineTurns');

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

// ── 1. preservation helper ───────────────────────────────────────────────────

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'outline-turns-'));
const fixture = path.join(tmpDir, 'track.json');
const curated = [
  { id: '1', number: 1, name: 'Abbey', short_name: 'Abbey', apex_s_m: 312, x: 1, y: 2,
    outward: [0, 1], tangent: [1, 0] },
];
fs.writeFileSync(fixture, JSON.stringify({ schema_version: 1, turns: curated }));

check('readExistingTurns returns the curated block', () => {
  const turns = readExistingTurns(fixture);
  assert(Array.isArray(turns));
  assert.strictEqual(turns.length, 1);
  assert.strictEqual(turns[0].name, 'Abbey');
});

check('withPreservedTurns restores turns a regeneration dropped', () => {
  const fresh = { schema_version: 1, centerline: [] };
  const merged = withPreservedTurns(fresh, fixture);
  assert.strictEqual(merged.turns.length, 1);
  assert.strictEqual(merged.turns[0].name, 'Abbey');
});

check('withPreservedTurns keeps freshly baked turns (does not clobber)', () => {
  const baked = [{ id: '9', number: 9, name: 'New', short_name: null, apex_s_m: 1, x: 0, y: 0,
                   outward: [0, 1], tangent: [1, 0] }];
  const merged = withPreservedTurns({ schema_version: 1, turns: baked }, fixture);
  assert.strictEqual(merged.turns.length, 1);
  assert.strictEqual(merged.turns[0].name, 'New');
});

check('withPreservedTurns is a no-op when nothing exists on disk', () => {
  const missing = path.join(tmpDir, 'nope.json');
  const outline = { schema_version: 1 };
  assert.deepStrictEqual(withPreservedTurns(outline, missing), { schema_version: 1 });
});

// ── 2. every outline writer wires the guard ──────────────────────────────────

const WRITERS = [
  'dev/scripts/prepare_all_outlines.js',
  'dev/scripts/auto_align_outline.js',
  'dev/scripts/compute_boundaries.js',
];
for (const rel of WRITERS) {
  check(`writer wires withPreservedTurns: ${rel}`, () => {
    const src = fs.readFileSync(path.join(ROOT, rel), 'utf8');
    assert(/require\(['"]\.\/lib\/outlineTurns['"]\)/.test(src), 'missing require of lib/outlineTurns');
    assert(/withPreservedTurns\(/.test(src), 'never calls withPreservedTurns');
    assert(!/JSON\.stringify\((?:outline|output), null, 2\)/.test(src),
      'still serialises an outline without withPreservedTurns');
  });
}

check('python outline writer preserves turns: dev/scripts/average_trajectory_outline.py', () => {
  const src = fs.readFileSync(path.join(ROOT, 'dev/scripts/average_trajectory_outline.py'), 'utf8');
  assert(/def preserve_turns\(/.test(src), 'helper missing');
  assert(/preserve_turns\(outline,\s*(str\()?output_path\)?\)/.test(src), 'helper never called');
});

// ── 3. baked turns are well-formed ───────────────────────────────────────────

const PLACEHOLDER = /^turn\s*\d+$/i;

function outlineFiles() {
  return fs.readdirSync(OUTLINES_DIR)
    .filter(f => f.endsWith('.json'))
    .map(f => path.join(OUTLINES_DIR, f))
    .filter(p => {
      try {
        return Boolean(JSON.parse(fs.readFileSync(p, 'utf8')).centerline);
      } catch {
        return false;
      }
    });
}

function validateTurns(outline, slug) {
  const turns = outline.turns;
  assert(Array.isArray(turns) && turns.length > 0, `${slug}: turns missing/empty`);
  const xs = outline.centerline.map(p => p.x);
  const ys = outline.centerline.map(p => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const slackX = (maxX - minX) * 0.05, slackY = (maxY - minY) * 0.05;
  const seenNumbers = new Set();
  for (const t of turns) {
    assert(typeof t.id === 'string' && t.id.length, `${slug}: bad id`);
    assert(Number.isInteger(t.number) && t.number >= 1, `${slug}: bad number ${t.number}`);
    assert(!seenNumbers.has(t.number), `${slug}: duplicate number ${t.number}`);
    seenNumbers.add(t.number);
    assert(t.name === null || (typeof t.name === 'string' && !PLACEHOLDER.test(t.name)),
      `${slug}: placeholder leaked into name for T${t.number}`);
    assert(t.short_name === null || typeof t.short_name === 'string',
      `${slug}: bad short_name for T${t.number}`);
    assert(Number.isFinite(t.apex_s_m) && t.apex_s_m > 0, `${slug}: bad apex_s_m`);
    assert(Number.isFinite(t.x) && Number.isFinite(t.y), `${slug}: non-finite anchor`);
    assert(t.x >= minX - slackX && t.x <= maxX + slackX, `${slug}: T${t.number} x outside bbox`);
    assert(t.y >= minY - slackY && t.y <= maxY + slackY, `${slug}: T${t.number} y outside bbox`);
    for (const key of ['outward', 'tangent']) {
      const v = t[key];
      assert(Array.isArray(v) && v.length === 2 && v.every(Number.isFinite),
        `${slug}: ${key} must be [x, y] numbers`);
      const len = Math.hypot(v[0], v[1]);
      assert(Math.abs(len - 1) < 0.02, `${slug}: ${key} not a unit vector (${len})`);
    }
    const dot = t.outward[0] * t.tangent[0] + t.outward[1] * t.tangent[1];
    assert(Math.abs(dot) < 0.05, `${slug}: outward/tangent not perpendicular (${dot})`);
  }
  const numbers = turns.map(t => t.number).sort((a, b) => a - b);
  numbers.forEach((n, i) => assert.strictEqual(n, i + 1, `${slug}: numbers not 1..n`));
  return turns;
}

const outlines = outlineFiles();
const withTurns = outlines.filter(p => {
  const o = JSON.parse(fs.readFileSync(p, 'utf8'));
  return Array.isArray(o.turns) && o.turns.length > 0;
});

check('at least one outline has a baked turns block', () => {
  assert(withTurns.length > 0, 'no outline carries `turns` yet — run dev/scripts/bake_outline_turns.py');
});

for (const p of withTurns) {
  check(`turns are valid: ${path.basename(p)}`, () => {
    validateTurns(JSON.parse(fs.readFileSync(p, 'utf8')), path.basename(p, '.json'));
  });
}

// ── 4. names agree with the coaching model used to bake them ─────────────────

// Grows as tracks are backfilled (slice 04).
const KNOWN = {
  'silverstone-international-circuit': 'silverstone-international-circuit_vista-af-corse-2026-21-lm.json',
};
for (const [slug, modelFile] of Object.entries(KNOWN)) {
  check(`turns match the coaching model: ${slug}`, () => {
    const outlinePath = path.join(OUTLINES_DIR, `${slug}.json`);
    const outline = JSON.parse(fs.readFileSync(outlinePath, 'utf8'));
    const model = JSON.parse(fs.readFileSync(path.join(MODELS_DIR, modelFile), 'utf8'));
    assert.strictEqual(outline.turns.length, model.corners.length,
      `turn count ${outline.turns.length} != model corners ${model.corners.length}`);
    outline.turns.forEach((t, i) => {
      const corner = model.corners[i];
      const expected = PLACEHOLDER.test(String(corner.name)) ? null : corner.name;
      assert.strictEqual(t.name, expected, `T${t.number} name mismatch`);
      assert.strictEqual(t.apex_s_m, Math.round(Number(corner.apex_s_m) * 10) / 10,
        `T${t.number} apex_s_m mismatch`);
    });
  });
}

// ── 5. generated ES module carries the turns ────────────────────────────────

check('static ES module for Silverstone International includes turns', () => {
  const modulePath = path.join(ROOT, 'product/web/js/staticSilverstoneInternationalCircuitOutlineData.js');
  const src = fs.readFileSync(modulePath, 'utf8');
  assert(src.includes('"turns"'), 'generated module has no turns — re-run register_outline.py / npm run build');
});

fs.rmSync(tmpDir, { recursive: true, force: true });

console.log(`\n${pass}/${pass + fail} assertions passed`);
if (fail > 0) {
  console.log('RESULT: FAIL');
  process.exit(1);
}
console.log('RESULT: PASS');
