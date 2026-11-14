// @parallel true
'use strict';
const { runPython } = require('./python');
const { pathToFileURL } = require('url');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
let failed = false;
function ok(value, label) {
  console.log(`${value ? '[PASS]' : '[FAIL]'} ${label}`);
  if (!value) failed = true;
}
const result = runPython([path.join(__dirname, 'test_silverstone_national_f296.py')], {
  encoding: 'utf8', timeout: 60000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product/python'), PYTHONUTF8: '1' },
});
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
ok(result.status === 0, 'Silverstone National / Ferrari 296 GT3 data contracts');
(async () => {
  // This slice is data-only: the map/web layer must resolve exactly as before.
  const { findOutlineByTrackName } = await import(pathToFileURL(
    path.join(ROOT, 'product/web/js/trackOutlineManifest.js')).href);
  const outline = findOutlineByTrackName('Silverstone National Circuit');
  ok(!!outline, 'runtime manifest still resolves the National simulator name');
  if (outline) {
    ok(outline.turns.map(turn => turn.name).join(',') ===
       'Copse,Maggots,Becketts,Brooklands,Luffield,Woodcote',
       'the mapped turns are unchanged by the new car model');
  }
  if (failed) process.exitCode = 1;
})().catch(error => { ok(false, error.stack); process.exitCode = 1; });
