// @parallel true
'use strict';
const { spawnSync } = require('child_process');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const res = spawnSync('python', [path.join(__dirname, 'test_curated_short_names.py')], {
  encoding: 'utf8', timeout: 60000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product/python'), PYTHONUTF8: '1' },
});
process.stdout.write(res.stdout || '');
process.stderr.write(res.stderr || '');
console.log(`${res.status === 0 ? '[PASS]' : '[FAIL]'} curated spoken names regression`);
if (res.status !== 0) process.exit(1);
