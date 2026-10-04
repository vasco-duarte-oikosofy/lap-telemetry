#!/usr/bin/env node
'use strict';
// @parallel true
// Thin wrapper (TESTING_LESSONS L12): run the Python coaching-model updater test.
const { spawnSync } = require('child_process');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const res = spawnSync('python3', [path.join(__dirname, 'test_update_coaching_model.py')], {
  encoding: 'utf8',
  timeout: 60000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product', 'python') },
});
process.stdout.write(res.stdout || '');
process.stderr.write(res.stderr || '');
if (res.error) { console.log(`  [FAIL] spawn — ${res.error.message}`); process.exit(1); }
process.exit(res.status || 0);
