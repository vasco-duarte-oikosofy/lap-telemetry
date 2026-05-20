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
