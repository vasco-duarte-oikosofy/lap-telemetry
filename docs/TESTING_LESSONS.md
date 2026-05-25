# Testing Lessons — Playwright / Headless Chromium

Read this file before writing a new test or debugging a failing one.

---

## L0. Every assertion must print `[PASS]` or `[FAIL]`

**Rule.** Every test script must print a `[PASS]` or `[FAIL]` line for each
assertion. This is the protocol that `run-tests-parallel.js` uses to count
assertions and detect failures. Tests that crash silently (exit non-zero with
no `[PASS]`/`[FAIL]` output) are invisible to the runner and **will be missed**.

```javascript
// ✗ Wrong — silent assertions, invisible to the runner
assert.deepStrictEqual(SPA_STATIC_OUTLINE, source);
assert.equal(parsed.schema_version, 0);
assert(svg.includes('left_boundary'), 'left boundary');
console.log('test passed');

// ✓ Right — every assertion reports itself
function ok(condition, label) {
  if (condition) { pass++; console.log(`  [PASS] ${label}`); }
  else           { fail++; console.log(`  [FAIL] ${label}`); }
}
ok(SPA_STATIC_OUTLINE != null, 'SPA_STATIC_OUTLINE is exported');
ok(parsed.schema_version === 0, `schema_version is 0 → ${parsed.schema_version}`);
```

**Exit code.** Every test must `process.exit(1)` on failure. The parallel
runner detects failures by both `[FAIL]` lines **and** non-zero exit codes.
A test that prints errors but exits 0 is a silent failure — the runner will
not catch it.

**Summary line.** Print a summary at the end:
```javascript
const total = pass + fail;
console.log(`\n  ${pass}/${total} assertions passed`);
if (fail > 0) { process.exit(1); }
```

**Why this matters.** The parallel runner (`run-tests-parallel.js`) counts
`[PASS]` lines to produce `ALL PASS — N assertions across M test scripts`.
It detects failures by `[FAIL]` lines or non-zero exit codes. Without these
patterns, a broken test looks like it passed.

---

## L1. Pass environment variables explicitly to subprocess spawns

**Problem.** When the test runner spawns child processes (e.g., Node.js tests that spawn Python via `spawnSync` or `spawn`), environment variables like `PYTHONPATH` are not automatically inherited. This causes intermittent failures where Python modules can't be found, even though the parent shell has `PYTHONPATH` set correctly.

**Symptom.** Tests fail with `ModuleNotFoundError: No module named 'lap_telemetry'` when run via the parallel runner, but pass when run directly with `PYTHONPATH` exported in the shell.

**Root cause.** Node.js `child_process.spawn()` does not inherit the parent's environment by default on all platforms. The `PYTHONPATH` set in `test-summary.sh` via `export` is lost when spawning child Node.js processes.

**Solution.** Always pass `env: { ...process.env }` in spawn options:

```javascript
// ✗ Wrong — environment variables may be lost
const child = spawn('node', [script], { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] });

// ✓ Right — explicitly inherit all environment variables
const child = spawn('node', [script], { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env } });
```

**For Python subprocesses spawned from Node.js tests:**

```javascript
// ✗ Wrong — PYTHONPATH may not be inherited
const res = spawnSync('python3', ['-c', code], { encoding: 'utf8', timeout: 30000 });

// ✓ Right — explicitly pass PYTHONPATH
const res = spawnSync('python3', ['-c', code], {
  encoding: 'utf8',
  timeout: 30000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product', 'python') }
});
```

**Why this matters.** The parallel test runner spawns many Node.js processes in parallel. If `PYTHONPATH` isn't inherited, Python-dependent tests will fail intermittently or timeout waiting for module imports. This is especially critical on CI where environment setup may differ from local development.

**Platform note.** This issue is more common on macOS and Windows than Linux. Linux often inherits environment variables by default, but relying on this is fragile. Always be explicit.

**Fast diagnosis.** If a Python-dependent test passes when run directly but fails in the parallel runner:
1. Check if the test spawns Python subprocesses
2. Verify `PYTHONPATH` is passed in spawn options
3. Add `env: { ...process.env }` to the spawn call

---

## L2. Use `.hover()` with relative positions, not `mouse.move()` with absolute coordinates

**Problem.** `page.mouse.move(box.x + box.width/2, box.y + box.height/2)` uses
absolute viewport coordinates. If the target element is below the viewport fold
(y > 720 px in Playwright's default 1280x720 viewport), headless Chromium
silently drops the event — no `mousemove` fires on any DOM element.

**Solution.** Use `element.hover({ position: { x, y } })` with element-relative
coordinates. `.hover()` auto-scrolls the element into view before dispatching.

```javascript
// Fragile: silent no-op when element is below the viewport
const box = await panelSvg.boundingBox();
await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);

// Robust: auto-scrolls, then dispatches at element-relative position
await panelSvg.hover({ position: { x: box.width / 2, y: box.height / 2 } });
```

---

## L3. Re-acquire elements after any re-render

**Problem.** `renderAll()` rebuilds the DOM via `panelsDiv.innerHTML = ''`.
Any element handle grabbed before a re-render (zoom, reset, lap change) is
now a detached node — `.boundingBox()` may return stale coordinates or null.

**Solution.** Re-query the element immediately before each interaction.

```javascript
// Fragile: panelSvg was grabbed before the zoom re-render
const panelBox = await panelSvg.boundingBox();  // stale / detached

// Robust: fresh handle after re-render
const freshPanel = await page.$('.panel-svg');
const box = await freshPanel.boundingBox();
```

---

## L4. Each test must own its scroll position

**Problem.** Tests that use `.hover()` (which scrolls) create a hidden
dependency: later tests pass only because an earlier test scrolled the page
into the right position. Reordering or skipping tests causes failures.

**Solution.** Every test section that interacts with mouse events on a
potentially-below-fold element must independently scroll into view via its
own `.hover()` call. Never assume the page is already scrolled.

```javascript
// Each section: re-acquire, scroll into view, interact
const panel = await page.$('.panel-svg');
await panel.hover({ position: { x: 1, y: 1 } });   // scroll into view
const box = await panel.boundingBox();                // now in-viewport
await page.mouse.move(box.x + box.width * 0.2, ...); // safe
```

---

## L5. Wait for data state, not just DOM elements

**Problem.** Waiting for a `<polyline>` to appear doesn't guarantee
`currentSessionBins` is populated. The element exists but the data
driving the tooltip / cursor dot isn't ready yet.

**Solution.** Wait for the actual data state:

```javascript
await page.waitForFunction(() => {
  return window.__getSessionKeys && window.__getSessionKeys().length > 0;
}, { timeout: 5000 });
```

---

## L6. Module-scoped variables aren't accessible in `page.evaluate()`

**Problem.** `currentSessionBins` is a `let` at module scope in `main.js`.
`page.evaluate(() => currentSessionBins)` throws `ReferenceError` because
Playwright evaluates in the page's global scope, not the module scope.

**Solution.** Expose debug helpers on `window` for test access:

```javascript
// main.js
window.__debugGetBins = () => ({ currentSessionBins, currentRefBins });

// test
const state = await page.evaluate(() => window.__debugGetBins());
```

---

## L7. Add debug logging before asserting

**Problem.** When a test fails, "FAIL: tooltip displayed" doesn't tell you
whether the tooltip was invisible, empty, or had wrong content.

**Solution.** Log state before the assertion:

```javascript
const tooltipText = await page.$eval('#tooltip', el => el.textContent);
console.log(`  Tooltip visible: ${tooltipVisible}`);
console.log(`  Tooltip text: ${tooltipText.slice(0, 200)}`);
assert(tooltipText.includes('dist:'), ...);
```

This turns "test failed" into "tooltip is visible but textContent is empty
string", which points directly at the root cause.

---

## L8. Screenshots are artifacts unless compared or asserted

**Problem.** Saving a screenshot can look like coverage, but it does not fail
the test unless the file is compared or at least checked. A scenario named
"pixel diff" that only writes a PNG gives false confidence.

**Solution.** Either use a real visual assertion/diff, or clearly label the
PNG as a manual artifact and assert the layout invariants in code. If writing
artifacts, verify the file was created and is non-empty.

```javascript
await page.screenshot({ path: shotPath });
const size = fs.statSync(shotPath).size;
assert(size > 0, 'screenshot artifact written', `${size} bytes`);
```

---

## L9. Be explicit about viewport width vs content/container width

**Problem.** A responsive test may say it is testing a 320px container while
actually setting a 420px viewport and relying on body padding/margins. That can
hide or invent overflow failures.

**Solution.** Define which width is under test. If testing content width, set
the viewport from the desired content width plus measured horizontal padding,
then assert the measured content width before checking layout.

```javascript
const paddingX = await page.evaluate(() => {
  const cs = getComputedStyle(document.body);
  return parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
});
await page.setViewportSize({ width: targetContentWidth + paddingX, height: 1200 });
```

---

## L10. Assert the visible renderer, not a hard-coded implementation element

**Problem.** A feature can switch between SVG and canvas rendering. Asserting
that `#circuit-map-svg` has a non-zero box fails when the canvas renderer is
visible, even though the map is correctly rendered.

**Solution.** Assert the visible rendering surface or accept all supported
surfaces, then keep implementation-specific checks limited to what they really
prove.

```javascript
const size = await page.evaluate(() => {
  const svg = document.getElementById('circuit-map-svg').getBoundingClientRect();
  const canvas = document.getElementById('track-heatmap-canvas').getBoundingClientRect();
  return Math.max(svg.width, canvas.width);
});
assert(size > 0, 'map renderer has visible width');
```

---

## L11. Regenerate static outline modules through the pipeline, not ad hoc scripts

**Problem.** Static outline modules are imported by name from
`trackOutlineManifest.js`. If an outline JSON is copied into a runtime module
with a different export name, many unrelated UI tests fail at bundle time with:

```text
No matching export in "...staticBahrainInternationalCircuitOutlineData.js"
for import "BAHRAIN_INTERNATIONAL_CIRCUIT_STATIC_OUTLINE"
```

That failure is not a rendering regression; it means the generated module and
manifest disagree before the app can load.

**Solution.** Always regenerate runtime outline modules with:

```bash
node dev/scripts/generate_outline_module.js product/data/track-outlines/<slug>.json
```

Do not hand-write `export const ...` names. The generator preserves the export
name already imported by `product/web/js/trackOutlineManifest.js` when the
module is registered, preventing manifest/module drift.

**Fast diagnosis.** If many browser tests fail after changing only a track
outline, run one failing script directly and look for esbuild import/export
errors before investigating Playwright behavior or reverting geometry data.

---

## L12. Python test scripts need a Node.js wrapper to join the parallel runner

**Problem.** `test-summary.sh` delegates to `run-tests-parallel.js`, which
 Discovers test scripts from `package.json` `scripts.test` and runs each with
`node`. A standalone Python test (`python3 dev/scripts/test_foo.py`) is
invisible to the runner — it will never be discovered or executed.

**Solution.** Create a thin Node.js wrapper that spawns the Python script and
follows the `[PASS]`/`[FAIL]` protocol:

```javascript
// @parallel true
'use strict';

const { spawnSync } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const PYTHONPATH = path.join(ROOT, 'product', 'python');
const script = path.join(ROOT, 'dev', 'scripts', 'test_foo.py');

let pass = 0, fail = 0;
function ok(condition, label) {
  if (condition) { pass++; console.log(`  [PASS] ${label}`); }
  else           { fail++; console.log(`  [FAIL] ${label}`); }
}

const res = spawnSync('python3', [script], {
  encoding: 'utf8',
  timeout: 60000,
  env: { ...process.env, PYTHONPATH },
});

process.stdout.write(res.stdout);
process.stderr.write(res.stderr);
ok(res.status === 0, `${path.basename(script)} exited 0`);

const total = pass + fail;
console.log(`\n  ${pass}/${total} assertions passed`);
if (fail > 0) { process.exit(1); }
```

Then add `node dev/scripts/test_foo.js` to `package.json` `scripts.test`.

**Why three things matter:**

1. **`// @parallel true`** — tells the runner this script can run in the
   parallel pool (no ordering dependency).

2. **`env: { ...process.env, PYTHONPATH }`** — `spawnSync` does not inherit
   the parent's environment by default. Without explicit `PYTHONPATH`, Python
   will fail with `ModuleNotFoundError`. (See L1 for the general rule.)

3. **The wrapper must contain `[PASS]`/`[FAIL]` in its source text.**
   `test_protocol_enforcement.js` does static analysis on `.js` source files —
   it checks that each registered test script contains those patterns.
   A wrapper that merely forwards Python output has no such patterns and
   will fail the protocol check. The `ok()` call + template literals that
   include `[PASS]` and `[FAIL]` satisfy the check.

**Standalone use.** The Python script can still be run directly:

```bash
python3 dev/scripts/test_foo.py
```

The wrapper only exists so the parallel runner can discover and execute it.

---

## L13. When a function gains a required parameter, grep for all call sites including embedded test strings

**Problem.** When `build_model()` gained a `detection_method` parameter in one slice, the test that calls it (`test_generate_track_coaching_model_from_reference.js`) wasn't updated. The test embeds Python code inside a JS template literal, so IDE "find usages" and refactoring tools don't discover the call site. The failure was a `TypeError: missing 1 required positional argument` that only appeared when the test ran.

**Symptom.** A test that used to pass starts failing with `TypeError: … missing N required positional argument(s)` after a signature change, and `grep` on `.py` files finds nothing because the call lives inside a `.js` file.

**Rule.** After changing any function signature in `product/python/`, search for all call sites across the entire repo — including `.js` files that embed Python:

```bash
grep -r "build_model\(" dev/ product/
```

Alternatively, always run the full suite after changing a public function's signature, not just the feature-specific tests. The parallel runner catches these within seconds.

**Why this matters.** Embedded-Python-in-JS wrappers (`L12`) are invisible to Python refactoring tools. The only reliable safety net is a `grep` across all file types or a full test run.

---

## L14. A failing test assertion may reveal an algorithm limitation, not a test bug

**Problem.** `test_losses_delta_time` asserts that `exit_distance_delta_m < 0` for a known loss at turn 3 exit. The assertion failed with `delta = 0.0`, which initially looked like a wrong test. Investigation showed the **algorithm** was the problem: `find_exit_points()` searched only from `apex_s_m` to `s_end_m` for brake release and full-throttle transitions. For short corners (apex-to-end ≤ 5 m), the real pedal transitions occur **past `s_end_m`** on the early straight. Both driver and reference fell back to the same boundary, yielding `delta = 0` — a meaningless value that says "we couldn't detect either exit point" rather than "they exited at the same point."

**Root cause.** Turn 3 at Barcelona has `apex_s_m = 1161`, `s_end_m = 1163` — a 2-metre search window. The driver's brake release at 1169 m and full throttle at 1175 m were outside the window. So were the reference's transitions. Both returned the fallback boundary (1163), producing `delta = 0`.

**Symptom.** A test that checks a sign convention (`delta < 0` for a loss) fails with `delta = 0.0`. The `loss_s` field is still correct (computed from delta-time), but `exit_distance_delta_m` is uninformative.

**Diagnosis.** Before concluding a test is wrong, ask: is the algorithm producing the best answer it can with the data available? If the output is a fallback value (boundary, `None`, `0.0`), the test may be correctly asserting a sign convention that the algorithm should satisfy but can't due to a search limitation.

**Fix.** Extend the search window past `s_end_m` by `exit_search_past_end_m` (default 50 m) so brake release and throttle transitions on the early straight are found. Added as a parameter on `PhaseDetectionThresholds` so it's configurable per-track if needed.

**Rule.** When a test fails with a default/fallback value, investigate whether the algorithm should have found a real value. A `0.0` or `None` that passes a weak assertion (`>= 0`) may be hiding the fact that the algorithm gave up too early.

---

## L15. Playwright tests are expensive — exclude by default, run with `--pw`

**Problem.** The full test suite (51 scripts) takes ~20 s, of which ~15 s comes
from 25 Playwright tests. Each PW test launches a Chromium process (~0.5–1 s
startup overhead), and even with concurrency of 8 the PW pool takes ~6–7 s
minimum. Most slices change Python or data-layer code and don't touch the UI
at all — yet every test run pays the full browser cost.

**Timing breakdown (typical, 10-core machine):**

| Category     | Count | Avg time | Concurrency | Pool time |
|--------------|-------|----------|-------------|-----------|
| Node (pure)  | 25    | ~0.1 s   | unlimited   | ~0.5 s    |
| Playwright   | 25    | ~1.7 s   | 8           | ~6–7 s    |
| Serial       | 1     | ~0.5 s   | 1           | ~0.5 s    |
| **Total**    | 51    |          |             | ~8–10 s   |

The slowest individual tests are all Playwright:
- `test_02_zoom_pan.js` — 2.5 s
- `test_f1f2.js` — 2.3 s
- `test_001_responsive.js` — 2.1 s
- `test_m6.js` — 2.1 s
- `test_m5.js` — 1.9 s

**Solution.** The test runner (`run-tests-parallel.js`) excludes Playwright
tests by default. This brings suite time down to ~5 s for typical slices
that don't change UI code.

```bash
bash scripts/test-summary.sh          # fast — Node + serial only (~5 s)
bash scripts/test-summary.sh --pw    # full — includes Playwright (~20 s)
```

**When to use `--pw`:**

1. Before completing every slice (per AGENTS.md).
2. When the slice changes UI code (`web/`, `dist/`).
3. After every 3rd slice within a mission (catch cross-layer regressions).

**Why not always include Playwright?** During active development on a
Python-only slice, running 25 browser processes per test cycle wastes
~15 s with zero chance of catching a regression. The fast suite catches
all Python- and Node-level regressions. UI regressions are only relevant
when UI code changes.
