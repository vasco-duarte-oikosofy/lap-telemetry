/**
 * Wrapper: runs the per-lap session debrief facts tests.
 * Run: node dev/scripts/test_session_debrief_facts.js
 */
// @parallel true

'use strict';

const { runPython } = require('./python');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const PYTHONPATH = [
  path.join(ROOT, 'product', 'python'),
  path.join(ROOT, 'dev', 'scripts'),
].join(path.delimiter);
const script = path.join(ROOT, 'dev', 'scripts', 'test_session_debrief_facts.py');

let pass = 0, fail = 0;
function ok(condition, label) {
  if (condition) { pass++; console.log(`  [PASS] ${label}`); }
  else           { fail++; console.log(`  [FAIL] ${label}`); }
}

const res = runPython([script], {
  encoding: 'utf8',
  timeout: 180000,
  env: { ...process.env, PYTHONPATH },
});

process.stdout.write(res.stdout);
process.stderr.write(res.stderr);
ok(res.status === 0, `${path.basename(script)} exited 0`);

const total = pass + fail;
console.log(`\n  ${pass}/${total} assertions passed`);
if (fail > 0) { process.exit(1); }
