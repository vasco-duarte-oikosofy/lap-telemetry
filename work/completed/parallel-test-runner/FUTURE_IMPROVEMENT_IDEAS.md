# Future Improvement Ideas

Ideas for further reducing full-suite wall-time (currently ~7s). Ordered
simplest-to-test first, hardest-to-test last.

---

## 1. Pre-build a warm HTTP server fixture (est. saves ~0.5–1s)

Start one HTTP server before any test runs, tear down after all finish.
Each Playwright test currently calls `startServer(WEB_DIR)` individually
(~5ms each, but it adds wiring complexity and prevents shared-state
optimisations). A single server also simplifies the shared-browser-context
approach (idea #6).

**Difficulty:** Low — refactor test-server into a beforeAll/afterAll fixture.
**Risk:** Low — server is stateless; test isolation is unaffected.

---

## 2. Skip `networkidle` in page loads (est. saves ~0.5s per test)

19 Playwright tests call `page.goto(url)` then `waitForLoadState('networkidle')`,
which waits until the network is idle for 500ms. Most tests don't need it —
they only need the JS app to be initialised. Replace with
`page.goto(url, { waitUntil: 'domcontentloaded' })` combined with a
`page.waitForFunction(() => window.__features)` or similar app-readiness
signal.

**Difficulty:** Low — per-test change, easy to verify individually.
**Risk:** Low — each test already has its own readiness check after load.

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

## 5. Batch `page.evaluate()` calls (est. saves ~1–3s)

Each Playwright test makes 15–22 `page.evaluate()` round-trips (~5–10ms
each). Batching related checks into a single `page.evaluate()` that returns
an object with all results cuts IPC calls from ~20 to ~5 per test. This
alone doesn't save much wall-time per test, but combined with shared browser
context (#6) it reduces the cumulative IPC overhead across 19 tests.

**Difficulty:** Medium — requires restructuring each test's assertion logic
into batched evaluate blocks.
**Risk:** Low — same assertions, just called in fewer round-trips. Each
test is independently verifiable.

---

## 6. Shared browser context across all Playwright tests (est. saves ~2–3s)

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

## 7. Use `jsdom` + `node-canvas` for headless rendering tests (est. saves ~1–2s)

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

## 8. Snapshot testing against pre-rendered screenshots (est. saves ~2–4s)

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