// @parallel true
'use strict';
const { spawnSync } = require('child_process');
const { pathToFileURL } = require('url');
const path = require('path');
const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
let failed = false;
function ok(value, label) {
  console.log(`${value ? '[PASS]' : '[FAIL]'} ${label}`);
  if (!value) failed = true;
}
const result = spawnSync('python', [path.join(__dirname, 'test_paul_ricard_1a.py')], {
  encoding: 'utf8', timeout: 60000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product/python'), PYTHONUTF8: '1' },
});
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
ok(result.status === 0, 'Paul Ricard 1A/P3 data contracts');
(async () => {
  const { findOutlineByTrackName } = await import(pathToFileURL(
    path.join(ROOT, 'product/web/js/trackOutlineManifest.js')).href);
  const outline = findOutlineByTrackName('Paul Ricard - 1A');
  ok(!!outline, 'runtime manifest resolves exact 1A simulator name');
  if (outline) {
    const { inferTrackNameFromFileName } = await import(pathToFileURL(
      path.join(ROOT, 'product/web/js/trackNameInference.js')).href);
    ok(findOutlineByTrackName(inferTrackNameFromFileName(
      'session_20261101T190458Z_paul-ricard---1a_lmu_race.parquet')) === outline,
      'filename-only replay resolves 1A despite inferred whitespace replacing the layout dash');
    ok(findOutlineByTrackName('paul-ricard---1a') === outline, 'recording slug resolves same 1A outline');
    ok(outline !== findOutlineByTrackName('Paul Ricard - 3A') &&
       outline !== findOutlineByTrackName('Paul Ricard - 1A-V2-Short'), 'existing layouts stay distinct');
    const source = JSON.parse(fs.readFileSync(path.join(ROOT,
      'product/data/track-outlines/paul-ricard---1a.json'), 'utf8'));
    ok(JSON.stringify(outline) === JSON.stringify(source), 'generated module exactly matches current source');
  }
  if (failed) process.exitCode = 1;
})().catch(error => { ok(false, error.stack); process.exitCode = 1; });
