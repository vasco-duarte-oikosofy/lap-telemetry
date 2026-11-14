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
