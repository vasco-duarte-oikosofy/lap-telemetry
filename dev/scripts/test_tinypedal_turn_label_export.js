#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Wrapper for dev/scripts/test_tinypedal_turn_label_export.py (TESTING_LESSONS L12:
 * Python tests join the Node suite through a thin wrapper that prints the
 * [PASS]/[FAIL] protocol lines).
 *
 * The exporter writes the turn-label files that the TinyPedal track map widget
 * reads, so its schema and its "no stale files" check are part of our suite.
 *
 * Run: node dev/scripts/test_tinypedal_turn_label_export.js
 */

const path = require('path');
const { runPython } = require('./python');

const ROOT = path.resolve(__dirname, '..', '..');
const SCRIPT = path.join(ROOT, 'dev', 'scripts', 'test_tinypedal_turn_label_export.py');

// `python3` alone is not portable: Windows may only have `py -3`/`python` (and a
// Store stub named `python3`), macOS usually has no `python`. See
// docs/TESTING_LESSONS.md L16 — resolve once through the shared helper.
let result;
try {
  result = runPython([SCRIPT], { cwd: ROOT, timeout: 120000 });
} catch (error) {
  console.log('  [FAIL] ' + error.message);
  console.log('\nRESULT: FAIL');
  process.exit(1);
}

const output = `${result.stdout || ''}${result.stderr || ''}`;
process.stdout.write(output);

const failed = /\[FAIL\]/.test(output) || result.status !== 0;
console.log(`\n${failed ? 'RESULT: FAIL' : 'RESULT: PASS'}`);
process.exit(failed ? 1 : 0);
