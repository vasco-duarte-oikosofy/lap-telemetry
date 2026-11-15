#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * The driver's shipped turn-label placements must survive into the widget.
 *
 * Runs the sibling TinyPedal test `tests/test_shipped_placements.py`, which
 * drives the real track-map widget and checks that a packaged
 * `label_offset_m` + `display_orientation` is adopted (and that a user
 * orientation still overrides it). Skips cleanly when the sibling checkout or
 * its Qt venv is not present, so the suite stays runnable on a bare clone.
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..', '..');
const TINY = path.resolve(ROOT, '../tinypedal');
let failed = false;

function ok(value, label) {
  console.log(`${value ? '[PASS]' : '[FAIL]'} ${label}`);
  if (!value) failed = true;
}

// Pin the actual driver input, not a second hand-written set of offsets.
const supplied = JSON.parse(fs.readFileSync(path.join(ROOT,
  'work/active/turn-label-editor/06-barcelona-placement/artifacts/driver-placement.json'), 'utf8'));
const presets = JSON.parse(fs.readFileSync(path.join(ROOT, 'dev/tools/turn-label-presets.json'), 'utf8'));
const preset = presets[supplied.track];
ok(supplied.version === 3 && supplied.display_orientation === 0 &&
  Object.keys(supplied.labels).length === 14, 'Barcelona input is v3, 0 degrees, 14 labels');
ok(JSON.stringify(preset?.labels) === JSON.stringify(supplied.labels),
  'Barcelona preset preserves every driver offset exactly');
ok(preset?.display_orientation === supplied.display_orientation,
  'Barcelona preset preserves the driver rotation');
const packagedPath = path.join(TINY, 'tinypedal/data/turn_labels/Circuit de Barcelona.turns.json');
if (fs.existsSync(packagedPath)) {
  const packaged = JSON.parse(fs.readFileSync(packagedPath, 'utf8'));
  const outline = JSON.parse(fs.readFileSync(path.join(ROOT,
    'product/data/track-outlines/circuit-de-barcelona.json'), 'utf8'));
  ok(packaged.display_orientation === supplied.display_orientation,
    'Barcelona packaged rotation matches the driver input');
  ok(packaged.turns.length === 14, 'Barcelona packages all 14 turns');
  outline.turns.forEach((turn, i) => {
    const offset = supplied.labels[turn.id];
    ok(JSON.stringify(packaged.turns[i]?.label_offset_m) === JSON.stringify([offset.dx_m, offset.dy_m]),
      `Barcelona ${turn.id}: packaged offset matches the driver input`);
  });
}

const binary = [path.join(TINY, '.venv/Scripts/python.exe'), path.join(TINY, '.venv/bin/python')]
  .find((candidate) => fs.existsSync(candidate));
const test = path.join(TINY, 'tests/test_shipped_placements.py');

if (!binary || !fs.existsSync(test)) {
  console.log('[SKIP] external TinyPedal checkout/Qt fixture unavailable');
} else {
  const result = spawnSync(binary, [test], {
    cwd: TINY, encoding: 'utf8', timeout: 180000, env: { ...process.env, PYTHONUTF8: '1' },
  });
  process.stdout.write(result.stdout || '');
  process.stderr.write(result.stderr || '');
  ok(result.status === 0, 'shipped turn-label placements reach the TinyPedal widget');
}

if (failed) process.exitCode = 1;
