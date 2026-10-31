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
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..', '..');
const SCRIPT = path.join(ROOT, 'dev', 'scripts', 'test_tinypedal_turn_label_export.py');

// `python3` is a Microsoft Store stub on Windows; `py` is the real launcher.
const CANDIDATES = process.platform === 'win32'
  ? [['py', ['-3']], ['python', []], ['python3', []]]
  : [['python3', []], ['python', []]];

const env = { ...process.env, PYTHONIOENCODING: 'utf-8' };

let result = null;
for (const [command, prefix] of CANDIDATES) {
  result = spawnSync(command, [...prefix, SCRIPT], { cwd: ROOT, encoding: 'utf8', timeout: 120000, env });
  if (!result.error) break;
}

if (!result || result.error) {
  console.log('  [FAIL] no Python interpreter found — ' + (result && result.error.message));
  console.log('\nRESULT: FAIL');
  process.exit(1);
}

const output = `${result.stdout || ''}${result.stderr || ''}`;
process.stdout.write(output);

const failed = /\[FAIL\]/.test(output) || result.status !== 0;
console.log(`\n${failed ? 'RESULT: FAIL' : 'RESULT: PASS'}`);
process.exit(failed ? 1 : 0);
