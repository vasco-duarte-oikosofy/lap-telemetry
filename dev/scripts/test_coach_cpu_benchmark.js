// @parallel true
'use strict';
const { spawnSync } = require('child_process');
const { runPython } = require('./python');
const path = require('path');
const root = path.resolve(__dirname, '../..');
const result = runPython([path.join(__dirname, 'test_coach_cpu_benchmark.py')], {
  cwd: root, encoding: 'utf8', timeout: 30000,
  env: { ...process.env, PYTHONPATH: path.join(root, 'product/python'), PYTHONUTF8: '1' },
});
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
console.log(`${result.status === 0 ? '[PASS]' : '[FAIL]'} coach CPU measurement/gate tests exited ${result.status}`);
if (result.status !== 0) process.exit(1);
