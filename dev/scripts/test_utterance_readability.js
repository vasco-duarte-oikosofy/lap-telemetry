// @parallel true
'use strict';

/**
 * Test utterance readability — bug 09.
 * Verifies that the prompt template contains rules for gain/loss
 * framing and gain-first ordering, and that the test corpus fixtures
 * load correctly into build_messages.
 */
const { spawnSync } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const PYTHONPATH = path.join(ROOT, 'product', 'python');
const script = path.join(ROOT, 'dev', 'scripts', 'test_utterance_readability.py');

let pass = 0, fail = 0;
function ok(condition, label) {
  if (condition) { pass++; console.log(`  [PASS] ${label}`); }
  else           { fail++; console.log(`  [FAIL] ${label}`); }
}

const res = spawnSync('python3', [script], {
  encoding: 'utf8',
  timeout: 60000,
  env: { ...process.env, PYTHONPATH },
});

process.stdout.write(res.stdout);
process.stderr.write(res.stderr);

ok(res.status === 0, `${path.basename(script)} exited 0`);

const total = pass + fail;
console.log(`\n  ${pass}/${total} assertions passed`);
if (fail > 0) { process.exit(1); }