// @parallel true
'use strict';
const { runPython } = require('./python');
const { pathToFileURL } = require('url');
const path = require('path');
const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');
let failed = false;
function ok(value, label) {
  console.log(`${value ? '[PASS]' : '[FAIL]'} ${label}`);
  if (!value) failed = true;
}
const result = runPython([path.join(__dirname, 'test_paul_ricard_elms.py')], {
  encoding: 'utf8', timeout: 60000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product/python'), PYTHONUTF8: '1' },
});
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
ok(result.status === 0, 'Paul Ricard ELMS/F296 data contracts');
(async () => {
  const { findOutlineByTrackName } = await import(pathToFileURL(
    path.join(ROOT, 'product/web/js/trackOutlineManifest.js')).href);
  const outline = findOutlineByTrackName('Paul Ricard - ELMS');
  ok(!!outline, 'runtime manifest resolves the exact ELMS simulator name');
  if (outline) {
    const { inferTrackNameFromFileName } = await import(pathToFileURL(
      path.join(ROOT, 'product/web/js/trackNameInference.js')).href);
    ok(findOutlineByTrackName(inferTrackNameFromFileName(
      'session_20261110T175322Z_paul-ricard---elms_lmu_practice.parquet')) === outline,
      'filename-only replay resolves ELMS despite the layout dash');
    ok(findOutlineByTrackName('paul-ricard---elms') === outline, 'recording slug resolves the same ELMS outline');
    ok(outline !== findOutlineByTrackName('Paul Ricard - 1A') &&
       outline !== findOutlineByTrackName('Paul Ricard - 1A-V2-Short') &&
       outline !== findOutlineByTrackName('Paul Ricard - 3A'), 'the other Paul Ricard layouts stay distinct');
    const source = JSON.parse(fs.readFileSync(path.join(ROOT,
      'product/data/track-outlines/paul-ricard---elms.json'), 'utf8'));
    ok(JSON.stringify(outline) === JSON.stringify(source), 'generated module exactly matches current source');
  }
  if (failed) process.exitCode = 1;
})().catch(error => { ok(false, error.stack); process.exitCode = 1; });
