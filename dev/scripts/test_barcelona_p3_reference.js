// @parallel true
'use strict';
const path = require('path');
const { runPython } = require('./python');
const ROOT = path.resolve(__dirname, '../..');
const result = runPython([path.join(__dirname, 'test_barcelona_p3_reference.py')], {
  encoding: 'utf8', timeout: 60000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product/python') },
});
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
const success = !result.error && result.status === 0;
console.log(`[${success ? 'PASS' : 'FAIL'}] Barcelona/P3 reference and curation contracts`);
if (!success) process.exitCode = 1;
