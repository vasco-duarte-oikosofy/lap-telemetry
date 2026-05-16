# Future Improvement Ideas

Ideas for further reducing full-suite wall-time (currently ~7s). Ordered
simplest-to-test first, hardest-to-test last.

---

## ✅ COMPLETED: Skip `networkidle` in page loads (saves ~0.5s per test)

**Status:** Implemented in F16 auto-zoom tests (slice 04.2).

Playwright tests now use `page.goto(url, { waitUntil: 'domcontentloaded' })`
combined with `page.waitForFunction(() => window.__features)` for app-readiness.
This eliminates the 500ms network idle wait that most tests don't need.

**Actual savings:** ~0.5s per test. Validated in `test_f16_bug10_bug11.js` and
`test_f16_auto_zoom_acceptance.js`.

**Pattern to copy:**
```javascript
await page.goto(url, { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => window.__features, { timeout: 5000 });
```

---

## ✅ COMPLETED: Batch `page.evaluate()` calls (saves ~50-80ms per test)

**Status:** Implemented in F16 auto-zoom tests (slice 04.2).

Batching related state reads into single `page.evaluate()` calls reduces IPC
round-trips from ~15-20 to ~5 per test. Each round-trip costs ~5-10ms overhead.

**Actual savings:** ~50-80ms per test. Validated in F16 tests.

**Pattern to copy:**
```javascript
const state = await page.evaluate(() => {
  const canvas = document.getElementById('track-heatmap-canvas');
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  const pixels = [];
  for (let py = 0; py < 10; py++) {
    for (let px = 0; px < 10; px++) {
      const x = Math.floor(w * (px + 1) / 11);
      const y = Math.floor(h * (py + 1) / 11);
      const d = ctx.getImageData(x, y, 1, 1).data;
      pixels.push({ r: d[0], g: d[1], b: d[2], a: d[3] });
    }
  }
  return {
    zoom: window.__getZoomRange(),
    mapState: window.__mapZoomPanState,
    canvas: { w, h, pixels },
  };
});
// Now use state.zoom, state.mapState, state.canvas
```

---

## ✅ COMPLETED: Replace `waitForTimeout()` with `waitForFunction()` (saves ~1-1.5s per test)

**Status:** Implemented in F16 auto-zoom tests (slice 04.2).

Tests previously used `waitForTimeout(300)` 5-6 times, adding ~1.5-1.8s of
artificial delay. Replacing with `waitForFunction()` that waits for actual
state changes reduces wait time to only what's needed (typically 10-50ms).

**Actual savings:** ~1-1.5s per test. Validated in F16 tests:
- `test_f16_bug10_bug11.js`: 3.0s → 1.3s (57% faster)
- `test_f16_auto_zoom_acceptance.js`: 3.0s → 0.9s (70% faster)

**Pattern to copy:**
```javascript
// Before: fixed delay
await page.evaluate(() => window.__setZoomRange(3000, 4000));
await page.waitForTimeout(300);  // Always waits 300ms

// After: wait for actual state
await page.evaluate(() => window.__setZoomRange(3000, 4000));
await page.waitForFunction(
  ([start, end]) => {
    const z = window.__getZoomRange();
    return z && z.start === start && z.end === end;
  },
  [3000, 4000],
  { timeout: 2000 }
);
```

**Key insight:** State-based waits are both faster AND more reliable than
fixed delays. They adapt to actual app performance rather than guessing.

---

## ✅ COMPLETED: Combine readiness checks in session loading (saves ~100-200ms per test)

**Status:** Implemented in F16 auto-zoom tests (slice 04.2).

Session loading previously used 3 sequential `waitForFunction()` calls:
1. Wait for session keys
2. Wait for panels rendered
3. Wait for zoom range ready

Combining checks 2+3 into a single `waitForFunction()` eliminates sequential
waiting overhead.

**Actual savings:** ~100-200ms per test.

**Pattern to copy:**
```javascript
// Keep session keys wait separate (prerequisite)
await page.waitForFunction(() => window.__getSessionKeys?.().length > 0, { timeout: 10000 });

// Pick laps
await page.evaluate(() => { /* ... */ });

// Combined readiness check for panels + zoom
await page.waitForFunction(() => {
  const panels = document.querySelectorAll('#panels .panel-svg');
  const zoom = window.__getZoomRange?.();
  return panels.length >= 2 && zoom != null;
}, { timeout: 10000 });
```

**Note:** Keep the session keys wait separate — it's the prerequisite for
everything else. Combining all three caused timeouts in testing.

---

## 1. Pre-build a warm HTTP server fixture (est. saves ~0.5–1s)

Start one HTTP server before any test runs, tear down after all finish.
Each Playwright test currently calls `startServer(WEB_DIR)` individually
(~5ms each, but it adds wiring complexity and prevents shared-state
optimisations). A single server also simplifies the shared-browser-context
approach (idea #2).

**Difficulty:** Low — refactor test-server into a beforeAll/afterAll fixture.
**Risk:** Low — server is stateless; test isolation is unaffected.

---

## 2. Shared browser context across all Playwright tests (est. saves ~2–3s)

**Now the highest-impact remaining idea.** After implementing ideas #2, #5,
and the `waitForTimeout` replacement in F16 tests (slice 04.2), shared
browser context would save an additional ~0.7s per test by eliminating
browser cold starts.

Every PW test launches its own `chromium.launch()` + HTTP server +
`page.goto()`. Measured overhead: ~0.73s per test (0.1s launch + 0.03s
context + 0.6s page load). Launching one browser and creating fresh
browser contexts per test (for isolation) reuses the process and avoids
repeated cold starts. Also reduces peak memory (no more 8 simultaneous
Chromium processes), allowing higher concurrency without swap.

**Difficulty:** Medium — requires a test harness that launches Chromium once
and passes a browser instance to each test. Tests must use `browser.newContext()`
instead of `chromium.launch()`. Biggest change is ensuring no state leaks
between contexts.
**Risk:** Medium — Playwright contexts are isolated by design, but any use
of `localStorage`, cookies, or service workers could cross boundaries
depending on browser version. Needs careful validation per test.

---

## 3. Shared Parquet fixture pool — build once (est. saves ~0.5–1s)

Multiple Node tests independently create the same Parquet fixtures via
`ParquetFixtureBuilder`. Each test's `.flush()` spawns Python. Building all
needed fixtures once in a "setup" phase and sharing paths to tests would
replace ~7 separate Python spawns with 1.

**Difficulty:** Low — extend ParquetFixtureBuilder to be reusable across
tests; add a setup step to the runner.
**Risk:** Low — fixtures are temp files with unique names; no state leakage.

---

## 4. Replace `spawnSync` with in-process calls (est. saves ~1–2s)

The 6 slow Node tests make **43 total `spawnSync` calls**, each spawning a
new Node or Python process (~50–100ms startup each). Most call
`spawnSync('node', [EXPORT_SCRIPT, ...])` to re-invoke CLI scripts and test
their output. Refactoring the CLI scripts to also export a callable function
lets tests import and call them directly, eliminating ~35 process spawns
and their startup overhead.

**Difficulty:** Medium — requires refactoring export scripts to dual-export
(a CLI entry point and a programmatic API), then updating each test.
**Risk:** Low — the CLI path still works; the in-process path is an
additional export. Easy to test: both paths must produce identical output.

---

## 5. Use `jsdom` + `node-canvas` for headless rendering tests (est. saves ~1–2s)

~8–10 Playwright tests don't need real browser interaction — they check
canvas pixel colours, DOM structure, or feature flags. These could run in
`jsdom` + `node-canvas` (Node packages) without Chromium, moving them from
the bounded PW pool to the unlimited Node pool. Only tests requiring real
interaction (hover, file upload, scroll events) stay as Playwright.

**Difficulty:** High — `jsdom` doesn't support layout, CSS paint, or real
event dispatch. Tests would need rewriting to mock `getBoundingClientRect`,
CSSOM, and canvas contexts. The rendering output won't match a real browser
pixel-for-pixel.
**Risk:** High — jsdom is not a real browser. Tests that pass in jsdom may
still fail in production (false negatives). Every test migrated needs a
"does this still catch real bugs?" audit.

---

## 6. Snapshot testing against pre-rendered screenshots (est. saves ~2–4s)

Replace most Playwright tests with a two-phase approach: (1) a "generate"
run that launches Chromium, exercises the app, and saves reference
screenshots + DOM snapshots; (2) subsequent runs compare captured output
against the references using `pixelmatch`. Only a handful of "integration"
tests still need a live browser. The rest become fast Node assertions on
PNG buffer data.

**Difficulty:** Very high — requires a snapshot management system, a CI
pipeline for updating golden files, and a review process for approving
changes. Deterministic rendering (fonts, timing, anti-aliasing) is hard to
guarantee across OS versions.
**Risk:** Very high — snapshot tests are notoriously flaky. Any OS-level
difference (font rendering, sub-pixel anti-aliasing, DPR changes) creates
false failures. The "generate" phase still needs to run sometimes, so you
haven't truly eliminated browser startup — just deferred it.
