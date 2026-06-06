# Bug 20 — Test suite fails on Windows: `python3` not found + ESM absolute-path imports

## Symptom

Running `bash scripts/test-summary.sh` on Windows produces 20 failures out of 30
scripts. All failures are pre-existing and fall into two distinct root causes;
none are related to business logic.

```
FAILED — 452 passed, 20 of 30 scripts failed
```

## Root cause A — `python3` command not found (14+ call sites)

Every test file that spawns Python calls `spawnSync('python3', ...)`. On Windows,
`python3` does not exist as a standalone command. The bare name resolves to the
Windows Store stub, which prints:

```
Python was not found; run without arguments to install from the Microsoft Store…
```

and exits with code 0 (not an error code), so the test runner sees a spurious
success followed by no output — it records the test as failed because no
assertions passed.

### Affected files

- `dev/scripts/parquet-fixture.js` (shared helper — fixing this unblocks all
  parquet-dependent tests automatically)
- `dev/scripts/test_bug13_authoritative_duration.js`
- `dev/scripts/test_bug16_slow_lap_guard.js`
- `dev/scripts/test_bug17_js_stale_boundary_frame.js`
- `dev/scripts/test_bug_python_regressions.js`
- `dev/scripts/test_coach_lap_comparison.js`
- `dev/scripts/test_contradictory_speed_coaching.js`
- `dev/scripts/test_corner_exit_coaching.js`
- `dev/scripts/test_delta_time_gains.js`
- `dev/scripts/test_generate_track_coaching_model_from_reference.js`
- `dev/scripts/test_js_pipeline_contract.js`
- `dev/scripts/test_phase_detection.js`
- `dev/scripts/test_apex_metrics_export.js`
- `dev/scripts/test_apex_metrics_ui.js`
- (and several more that inherit from `parquet-fixture.js`)

## Root cause B — ESM dynamic `import()` rejects Windows absolute paths (5 call sites)

Node.js's ESM loader only accepts `file://` URLs or relative specifiers as dynamic
import targets. On Windows, `path.join(ROOT, 'product/web/js/file.js')` produces
a bare `C:\Users\...` path, which the loader rejects:

```
Error [ERR_UNSUPPORTED_ESM_URL_SCHEME]: Only URLs with a scheme in: file, data,
and node are supported by the default ESM loader. On Windows, absolute paths
must be valid file:// URLs.
```

### Affected files

- `dev/scripts/test_apex_annotations.js`
- `dev/scripts/test_apex_metrics.js`
- `dev/scripts/test_apex_metrics_aggregate.js`
- `dev/scripts/test_apex_metrics_surface_terrain.js`
- `dev/scripts/test_static_outline_runtime_rendering.js`

## Proposed fix

### A — Central `pythonBin()` helper

Create `dev/scripts/python-bin.js` that resolves the correct Python executable
once and exports it:

```js
const path = require('path');
const fs = require('fs');
const ROOT = path.resolve(__dirname, '../..');

function pythonBin() {
  if (process.env.PYTHON_BIN) return process.env.PYTHON_BIN;
  const venv = process.platform === 'win32'
    ? path.join(ROOT, '.venv', 'Scripts', 'python.exe')
    : path.join(ROOT, '.venv', 'bin', 'python3');
  if (fs.existsSync(venv)) return venv;
  return process.platform === 'win32' ? 'python' : 'python3';
}

module.exports = { pythonBin };
```

Resolution order:
1. `PYTHON_BIN` env var — lets CI or `test-summary.sh` pin the interpreter
2. `.venv/Scripts/python.exe` (Windows) / `.venv/bin/python3` (Unix) — picks up
   the project venv automatically when running from the repo root
3. `python` / `python3` — system fallback

Every `spawnSync('python3', ...)` call in the affected files becomes
`spawnSync(pythonBin(), ...)` with a `require('./python-bin')` at the top.

`test-summary.sh` also exports the venv Python so the shell-invoked path is
consistent:

```bash
export PYTHON_BIN="$(python3 -c 'import sys; print(sys.executable)')"
```

### B — `pathToFileURL` for dynamic ESM imports

Replace bare-path `import()` calls with proper `file://` URLs using Node's
built-in `pathToFileURL`:

```js
// Before
const mod = await import(path.join(ROOT, 'product/web/js/file.js'));

// After
const { pathToFileURL } = require('url');
const mod = await import(pathToFileURL(path.join(ROOT, 'product/web/js/file.js')).href);
```

The five affected files each have one or two such calls. No other logic changes.
