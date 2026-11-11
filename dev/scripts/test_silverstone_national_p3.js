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
const result = runPython([path.join(__dirname, 'test_silverstone_national_p3.py')], {
  encoding: 'utf8', timeout: 60000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product/python'), PYTHONUTF8: '1' },
});
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
ok(result.status === 0, 'Silverstone National / Ginetta P3 data contracts');
(async () => {
  const { findOutlineByTrackName } = await import(pathToFileURL(
    path.join(ROOT, 'product/web/js/trackOutlineManifest.js')).href);
  const outline = findOutlineByTrackName('Silverstone National Circuit');
  ok(!!outline, 'runtime manifest resolves the exact National simulator name');
  if (outline) {
    const { inferTrackNameFromFileName } = await import(pathToFileURL(
      path.join(ROOT, 'product/web/js/trackNameInference.js')).href);
    ok(findOutlineByTrackName(inferTrackNameFromFileName(
      'session_20261111T172218Z_silverstone-national-circuit_lmu_practice.parquet')) === outline,
      'filename-only replay resolves the National layout');
    ok(findOutlineByTrackName('silverstone-national-circuit') === outline,
      'recording slug resolves the same National outline');
    ok(outline !== findOutlineByTrackName('Silverstone International Circuit') &&
       outline !== findOutlineByTrackName('Silverstone Grand Prix Circuit - ELMS'),
      'International and GP-ELMS stay distinct layouts with their own outlines');
    const source = JSON.parse(fs.readFileSync(path.join(ROOT,
      'product/data/track-outlines/silverstone-national-circuit.json'), 'utf8'));
    ok(JSON.stringify(outline) === JSON.stringify(source),
      'generated module exactly matches current source');
  }
  if (failed) process.exitCode = 1;
})().catch(error => { ok(false, error.stack); process.exitCode = 1; });
