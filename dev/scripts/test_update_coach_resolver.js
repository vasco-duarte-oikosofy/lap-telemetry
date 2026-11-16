#!/usr/bin/env node
'use strict';
// @parallel true
// Thin wrapper (TESTING_LESSONS L12): run the /update_coach resolver gate test.
const { runPython } = require('./python');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const res = runPython([path.join(__dirname, 'test_update_coach_resolver.py')], {
  encoding: 'utf8',
  timeout: 120000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product/python'), PYTHONUTF8: '1' },
});
process.stdout.write(res.stdout || '');
process.stderr.write(res.stderr || '');
if (res.error) { console.log(`  [FAIL] spawn — ${res.error.message}`); process.exit(1); }
process.exit(res.status || 0);
