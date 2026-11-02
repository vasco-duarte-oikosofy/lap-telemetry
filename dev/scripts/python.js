'use strict';
/**
 * One place that finds a real Python 3 interpreter, for every Node script and
 * test wrapper in this repo.
 *
 * Why this exists (see docs/TESTING_LESSONS.md L16/L17):
 * - Windows ships a `python3.exe` App Execution Alias that is NOT Python: it
 *   prints "Python was not found" and exits 9009. `python` may be missing too
 *   while the `py` launcher works.
 * - macOS/Linux usually have `python3` and no `python`.
 * - Python prints Unicode corner names (Hôtel, Ste-Baume) that crash the
 *   Windows cp1252 console unless UTF-8 mode is forced.
 *
 * So never spawn a bare `python`/`python3` in a script. Use:
 *
 *   const { runPython } = require('./python');
 *   const res = runPython([script], { timeout: 60000 });
 *
 * Override the interpreter with LAP_TELEMETRY_PYTHON=/path/to/python3.
 * From the shell: `$(node dev/scripts/python.js)` prints the command to run.
 */
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const PROBE = 'import sys; print(sys.version_info[0])';
const OVERRIDE_ENV = 'LAP_TELEMETRY_PYTHON';
const ROOT = path.resolve(__dirname, '..', '..');

let cached = null;

function candidates() {
  const override = process.env[OVERRIDE_ENV];
  if (override) return [[override, []]];
  // The project venv first (docs/SETUP.md), then whatever the platform calls Python.
  // `py -3` is the python.org launcher; the App Execution Alias stubs come last.
  const venv = [path.join(ROOT, '.venv/bin/python'), path.join(ROOT, '.venv/Scripts/python.exe')]
    .filter((candidate) => fs.existsSync(candidate));
  const system = process.platform === 'win32'
    ? [['py', ['-3']], ['python', []], ['python3', []]]
    : [['python3', []], ['python', []]];
  return [...venv.map((interpreter) => [interpreter, []]), ...system];
}

function utf8Env(overrides) {
  return {
    ...process.env,
    ...overrides,
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8',
  };
}

/** Resolve `{ command, prefix }` once per process; throws if no Python 3 is usable. */
function resolvePython() {
  if (cached) return cached;
  const attempts = [];
  for (const [command, prefix] of candidates()) {
    const probe = spawnSync(command, [...prefix, '-c', PROBE], {
      encoding: 'utf8', timeout: 20000, env: utf8Env(),
    });
    const status = probe.error ? probe.error.code : probe.status;
    if (!probe.error && probe.status === 0 && String(probe.stdout).trim() === '3') {
      cached = { command, prefix };
      return cached;
    }
    attempts.push(`${[command, ...prefix].join(' ')} -> ${status}`);
  }
  throw new Error(
    `No Python 3 interpreter found (${attempts.join(', ')}). ` +
    `Install Python 3 or set ${OVERRIDE_ENV} to its full path.`);
}

/** spawnSync() with the resolved interpreter, UTF-8 forced, options passed through. */
function runPython(args, options = {}) {
  const { command, prefix } = resolvePython();
  return spawnSync(command, [...prefix, ...args], {
    encoding: 'utf8',
    ...options,
    env: utf8Env(options.env),
  });
}

module.exports = { resolvePython, runPython, utf8Env };

if (require.main === module) {
  try {
    const { command, prefix } = resolvePython();
    console.log([command, ...prefix].join(' '));
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}
