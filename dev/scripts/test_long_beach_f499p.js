// @parallel true
'use strict';
const { spawnSync } = require('child_process');
const { runPython } = require('./python');
const { pathToFileURL } = require('url');
const path = require('path');
const fs = require('fs');
const ROOT = path.resolve(__dirname, '..', '..');
let failed = false;
function ok(value, label) {
  console.log(`${value ? '[PASS]' : '[FAIL]'} ${label}`);
  if (!value) failed = true;
}
const res = runPython([path.join(__dirname, 'test_long_beach_f499p.py')], {
  encoding: 'utf8', timeout: 60000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product/python'), PYTHONUTF8: '1' },
});
process.stdout.write(res.stdout || '');
process.stderr.write(res.stderr || '');
ok(res.status === 0, 'Long Beach 499P data contracts');
(async () => {
  const { findOutlineByTrackName } = await import(pathToFileURL(
    path.join(ROOT, 'product/web/js/trackOutlineManifest.js')).href);
  const outline = findOutlineByTrackName('Grand Prix of Long Beach');
  ok(!!outline, 'runtime manifest resolves the exact LMU track name');
  ok(findOutlineByTrackName('grand-prix-of-long-beach') === outline,
    'runtime manifest resolves the recording slug');
  if (outline) {
    ok(outline.turns?.length === 11, 'generated runtime copy retains all 11 turn anchors');
    const source = JSON.parse(fs.readFileSync(path.join(ROOT,
      'product/data/track-outlines/grand-prix-of-long-beach.json'), 'utf8'));
    ok(JSON.stringify(outline) === JSON.stringify(source), 'generated module exactly matches the source outline');
  }
  if (failed) process.exitCode = 1;
})().catch(err => { ok(false, err.stack); process.exitCode = 1; });
