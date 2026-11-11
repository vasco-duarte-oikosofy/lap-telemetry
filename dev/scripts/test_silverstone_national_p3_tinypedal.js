// @parallel true
'use strict';
const { runPython } = require('./python');
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const TINY = path.resolve(ROOT, '../tinypedal');
let failed = false;
function ok(value, label) {
  console.log(`${value ? '[PASS]' : '[FAIL]'} ${label}`);
  if (!value) failed = true;
}
const check = runPython(['-c', `
import json, sys
sys.path.insert(0, 'dev/scripts')
from export_turn_labels_for_tinypedal import build_payload
o = json.loads(open('product/data/track-outlines/silverstone-national-circuit.json', encoding='utf8').read())
d = build_payload(o, 'Silverstone National Circuit')
assert len(d['turns']) == 6, len(d['turns'])
assert all(t['s_frac'] == round(c['apex_s_m'] / o['lap_length_m'], 6) for t, c in zip(d['turns'], o['turns']))
assert [t['name'] for t in d['turns']] == [t['name'] for t in o['turns']]
assert d['lap_length_m'] == round(o['lap_length_m'], 3)
print('[PASS] isolated National export preserves all six names and same-axis fractions')
`], { cwd: ROOT, encoding: 'utf8', timeout: 30000, env: { ...process.env, PYTHONUTF8: '1' } });
process.stdout.write(check.stdout || '');
process.stderr.write(check.stderr || '');
ok(check.status === 0, 'isolated National turn export contract');
const binary = [path.join(TINY, '.venv/Scripts/python.exe'), path.join(TINY, '.venv/bin/python')]
  .find(p => fs.existsSync(p));
if (binary && fs.existsSync(path.join(TINY, 'trackmap/Silverstone National Circuit.svg'))) {
  const result = spawnSync(binary, [path.join(TINY, 'tests/test_silverstone_national_turn_labels.py'),
    '--outline', path.join(ROOT, 'product/data/track-outlines/silverstone-national-circuit.json'),
    '--save', path.join(ROOT, 'var/tmp/silverstone-national-tinypedal'),
  ], { cwd: TINY, encoding: 'utf8', timeout: 120000, env: { ...process.env, PYTHONUTF8: '1' } });
  process.stdout.write(result.stdout || '');
  process.stderr.write(result.stderr || '');
  ok(result.status === 0, 'National real TinyPedal widget regression');
} else {
  console.log('[SKIP] external TinyPedal Qt/map fixture unavailable; isolated National export still tested');
}
if (failed) process.exitCode = 1;
