// @parallel true
'use strict';
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const ROOT = path.resolve(__dirname, '../..');
const TINY = path.resolve(ROOT, '../tinypedal');
let failed = false;
function ok(value, label) {
  console.log(`${value ? '[PASS]' : '[FAIL]'} ${label}`);
  if (!value) failed = true;
}
const check = spawnSync('python', ['-c', `
import json,sys
from pathlib import Path
sys.path.insert(0,'dev/scripts')
from export_turn_labels_for_tinypedal import build_payload
p=Path('product/data/track-outlines/paul-ricard---1a.json')
o=json.loads(p.read_text(encoding='utf8'));d=build_payload(o,'Paul Ricard - 1A')
assert len(d['turns'])==14
assert all(t['s_frac']==round(c['apex_s_m']/o['lap_length_m'],6) for t,c in zip(d['turns'],o['turns']))
assert [t['name'] for t in d['turns']]==[t['name'] for t in o['turns']]
print('[PASS] isolated 1A export preserves all 14 names and same-axis fractions')
`], { cwd: ROOT, encoding: 'utf8', timeout: 30000, env: { ...process.env, PYTHONUTF8: '1' } });
process.stdout.write(check.stdout || '');
process.stderr.write(check.stderr || '');
ok(check.status === 0, 'isolated 1A turn export contract');
const binary = [path.join(TINY, '.venv/Scripts/python.exe'), path.join(TINY, '.venv/bin/python')]
  .find(p => fs.existsSync(p));
if (binary && fs.existsSync(path.join(TINY, 'trackmap/Paul Ricard - 1A.svg'))) {
  const result = spawnSync(binary, [path.join(TINY, 'tests/test_paul_ricard_1a_turn_labels.py'),
    '--outline', path.join(ROOT, 'product/data/track-outlines/paul-ricard---1a.json'),
    '--save', path.join(ROOT, 'var/tmp/paul-ricard-1a-tinypedal'),
  ], { cwd: TINY, encoding: 'utf8', timeout: 120000, env: { ...process.env, PYTHONUTF8: '1' } });
  process.stdout.write(result.stdout || '');
  process.stderr.write(result.stderr || '');
  ok(result.status === 0, '1A real TinyPedal widget regression');
} else {
  console.log('[SKIP] external TinyPedal Qt/map fixture unavailable; isolated 1A export still tested');
}
if (failed) process.exitCode = 1;
