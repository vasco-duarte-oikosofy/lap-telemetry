// @parallel true
'use strict';
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const root = path.resolve(__dirname, '../..');
const tiny = path.resolve(root, '../tinypedal');
let failed = false;
function run(binary, script, args, cwd) {
  const result = spawnSync(binary, [script, ...args], {
    cwd, encoding: 'utf8', timeout: 120000,
    env: { ...process.env, PYTHONUTF8: '1' },
  });
  process.stdout.write(result.stdout || '');
  process.stderr.write(result.stderr || '');
  console.log(`${result.status === 0 ? '[PASS]' : '[FAIL]'} ${path.basename(script)} exited ${result.status}`);
  if (result.status !== 0) failed = true;
}
run('python', path.join(__dirname, 'test_long_beach_tinypedal.py'), [], root);
const binary = [path.join(tiny, '.venv/Scripts/python.exe'), path.join(tiny, '.venv/bin/python')]
  .find(candidate => fs.existsSync(candidate));
if (binary && fs.existsSync(path.join(tiny, 'trackmap/Grand Prix of Long Beach.svg'))) {
  run(binary, path.join(tiny, 'tests/test_long_beach_turn_labels.py'), [
    '--outline', path.join(root, 'product/data/track-outlines/grand-prix-of-long-beach.json'),
    '--save', path.join(root, 'var/tmp/long-beach-tinypedal'),
  ], tiny);
  if (process.env.LONG_BEACH_TINY_ALL_TESTS === '1') {
    for (const script of ['test_turn_labels.py', 'test_turn_labels_render.py', 'test_track_map_widget_labels.py']) {
      run(binary, path.join(tiny, 'tests', script), [], tiny);
    }
  }
} else {
  console.log('[SKIP] external TinyPedal Qt/map fixture unavailable; isolated exporter regressions still ran');
}
if (failed) process.exitCode = 1;
