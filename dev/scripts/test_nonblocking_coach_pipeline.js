// @parallel true
'use strict';

/**
 * Test non-blocking coach pipeline (bug 07, option C: dual-path).
 *
 * Node.js wrapper that spawns the Python test script so the parallel
 * runner can discover and execute it.
 */
const { spawnSync } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const PYTHONPATH = path.join(ROOT, 'product', 'python');
const script = path.join(ROOT, 'dev', 'scripts', 'test_nonblocking_coach_pipeline.py');

let pass = 0, fail = 0;
function ok(condition, label) {
  if (condition) { pass++; console.log(`  [PASS] ${label}`); }
  else           { fail++; console.log(`  [FAIL] ${label}`); }
}

const res = spawnSync('python3', [script], {
  encoding: 'utf8',
  timeout: 120000,
  env: { ...process.env, PYTHONPATH },
});

// Forward the Python script's output so the runner can count [PASS]/[FAIL].
process.stdout.write(res.stdout);
process.stderr.write(res.stderr);

// Also check exit code — a crashed Python script may produce no [FAIL] lines.
ok(res.status === 0, `${path.basename(script)} exited 0`);

const total = pass + fail;
console.log(`\n  ${pass}/${total} assertions passed`);
if (fail > 0) { process.exit(1); }