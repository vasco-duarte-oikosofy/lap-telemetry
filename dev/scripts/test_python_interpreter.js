// @parallel true
'use strict';
/**
 * Guards the single-source-of-truth Python resolver (dev/scripts/python.js).
 *
 * Regression this prevents: scripts spawning a bare `python3`, which on Windows
 * is often the Microsoft Store stub (exit 9009), or a bare `python`, which macOS
 * does not ship. Also guards the UTF-8 forcing that keeps accented corner names
 * printing on a cp1252 console.
 */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const { resolvePython, runPython } = require('./python');

let pass = 0;
let fail = 0;
function ok(condition, label, detail = '') {
  if (condition) {
    pass += 1;
    console.log(`  [PASS] ${label}`);
  } else {
    fail += 1;
    console.log(`  [FAIL] ${label}${detail ? ` — ${detail}` : ''}`);
  }
}

const ROOT = path.resolve(__dirname);
const ALLOWED = new Set(['python.js', 'test_python_interpreter.js']); // the resolver and this guard

// A bare interpreter spawn: spawnSync('python3'|'python'), spawn(py), etc.
const BARE = /(?:spawn|spawnSync|exec|execSync|execFileSync)\(\s*['"](?:python|python3|py)['"]/;

const offenders = [];
for (const name of fs.readdirSync(ROOT)) {
  if (!name.endsWith('.js') || ALLOWED.has(name)) continue;
  const text = fs.readFileSync(path.join(ROOT, name), 'utf8');
  if (BARE.test(text)) offenders.push(name);
}
ok(offenders.length === 0,
  'no script spawns a bare python/python3/py interpreter',
  offenders.join(', '));

const { command, prefix } = resolvePython();
const version = runPython(['--version']);
ok(version.status === 0 && /Python 3\./.test(version.stdout || version.stderr),
  `resolved interpreter reports Python 3 (${[command, ...prefix].join(' ')})`,
  String(version.stdout || version.stderr));

const unicode = runPython(['-c', 'print("Hôtel → Sainte-Baume ✓")']);
ok(unicode.status === 0 && (unicode.stdout || '').includes('Hôtel → Sainte-Baume ✓'),
  'spawned Python prints non-ASCII without a cp1252 crash',
  unicode.stderr || '');

// An unusable override must fail loudly with guidance, not fall back silently.
const overridden = spawnSync(process.execPath, ['-e', `
  const { resolvePython } = require(${JSON.stringify(path.join(ROOT, 'python.js'))});
  try { resolvePython(); console.log('resolved-anyway'); }
  catch (error) { console.log(error.message); process.exit(7); }
`], {
  encoding: 'utf8',
  env: { ...process.env, LAP_TELEMETRY_PYTHON: path.join(ROOT, 'definitely-not-python') },
});
ok(overridden.status === 7 && /LAP_TELEMETRY_PYTHON/.test(overridden.stdout || ''),
  'a broken LAP_TELEMETRY_PYTHON override fails with a clear message',
  overridden.stdout?.trim());

// The CLI form used by shell scripts must print a runnable command.
const cli = spawnSync(process.execPath, [path.join(ROOT, 'python.js')], { encoding: 'utf8' });
ok(cli.status === 0 && cli.stdout.trim().length > 0,
  '`node dev/scripts/python.js` prints the interpreter command',
  cli.stderr?.trim());

assert.ok(pass > 0);
console.log(`\n  ${pass}/${pass + fail} assertions passed`);
if (fail > 0) process.exitCode = 1;
