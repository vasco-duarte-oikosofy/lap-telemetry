// @parallel true
'use strict';
const { runPython } = require('./python');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
let failed = false;
function ok(value, label) {
  console.log(`${value ? '[PASS]' : '[FAIL]'} ${label}`);
  if (!value) failed = true;
}
const result = runPython([path.join(__dirname, 'test_rear_grip_signal.py')], {
  encoding: 'utf8', timeout: 120000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product/python'), PYTHONUTF8: '1' },
});
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
ok(result.status === 0, 'rear grip signal: measured refusal + new recorder columns');
if (failed) process.exitCode = 1;
