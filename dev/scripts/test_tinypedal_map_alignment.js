// @parallel true
'use strict';
const { runPython } = require('./python');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const res = runPython([path.join(__dirname, 'test_tinypedal_map_alignment.py')], {
  encoding: 'utf8', timeout: 60000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product/python'), PYTHONUTF8: '1' },
});
process.stdout.write(res.stdout || '');
process.stderr.write(res.stderr || '');
console.log(`${res.status === 0 ? '[PASS]' : '[FAIL]'} TinyPedal map start-line alignment regression`);
if (res.status !== 0) process.exit(1);
