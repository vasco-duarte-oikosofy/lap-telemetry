// @parallel true
'use strict';
const { spawnSync } = require('child_process');
const path = require('path');
const root = path.resolve(__dirname, '../..');
const result = spawnSync('python', [path.join(__dirname, 'test_live_utterance_cpu.py')], {
  cwd: root, encoding: 'utf8', timeout: 60000,
  env: { ...process.env, PYTHONPATH: path.join(root, 'product/python'), PYTHONUTF8: '1' },
});
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
console.log(`${result.status === 0 ? '[PASS]' : '[FAIL]'} live utterance CPU reporting tests exited ${result.status}`);
if (result.status !== 0) process.exit(1);
