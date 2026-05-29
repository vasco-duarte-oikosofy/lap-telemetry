#!/usr/bin/env node
'use strict';
// @parallel true

const { spawnSync } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const PYTHONPATH = path.join(ROOT, 'product', 'python');
const tests = [
  'dev/scripts/test_bug10b.py',
  'dev/scripts/test_bug10c.py',
  'dev/scripts/test_bug11.py',
  'dev/scripts/test_bug12.py',
  'dev/scripts/test_bug14.py',
];

let pass = 0;
let fail = 0;
function ok(condition, label, detail = '') {
  if (condition) { pass++; console.log(`  [PASS] ${label}${detail ? ' — ' + detail : ''}`); }
  else { fail++; console.log(`  [FAIL] ${label}${detail ? ' — ' + detail : ''}`); }
}

const res = spawnSync('python3', ['-m', 'pytest', '-q', ...tests], {
  cwd: ROOT,
  encoding: 'utf8',
  timeout: 120000,
  env: { ...process.env, PYTHONPATH },
});

process.stdout.write(res.stdout || '');
process.stderr.write(res.stderr || '');
ok(!res.error, 'pytest bug regression tests spawned', res.error?.message || '');
ok(res.status === 0, 'pytest bug regression tests exited 0', res.status === 0 ? '' : `status ${res.status}`);

const total = pass + fail;
console.log(`\n  ${pass}/${total} assertions passed`);
if (fail > 0) process.exit(1);
