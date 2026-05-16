# Slice 02 — Learnings

## What surprised us

1. **Three silently-broken tests.** The old bash runner used `|| true` on child processes and only detected failures via `[FAIL]` regex patterns. Three tests crashed with unhandled errors (exit 1) but produced zero `[FAIL]` lines, so the old runner counted them as passing with 0 assertions. This meant the suite reported "798 assertions across 36 test scripts" when it should have reported failures:
   - `test_static_outline_runtime_rendering.js` — imported a removed function `getSpaStaticOutline`
   - `test_m6_extras.js` — `WEB_DIR` pointed to `web/` instead of `product/web/` (broken by repo reorganization)
   - `test_manual_outline_align.js` — HTML path was `tools/` instead of `dev/tools/`

2. **Exit-code detection is essential.** The parallel runner checks both `[FAIL]` patterns and non-zero exit codes. This caught the three broken tests that the old runner missed.

3. **PYTHONPATH must be set in the wrapper.** `test_m6.js` needs `PYTHONPATH` to find the `lap_telemetry` Python module. The old bash script exported it; the new Node runner inherits it from the bash wrapper.

4. **`test_m6_extras.js` used `REPO` instead of `ROOT`.** Inconsistent variable naming — other tests use `ROOT`. Fixed during this slice.

5. **Speed: 42s → 17s.** Bounded concurrency of 6 on a 14-core Mac. Most of the time is Playwright browser startup (~2-3s per test). The 18 Node tests finish almost instantly.

6. **Line count of runner: 153 lines.** Well under the 200-line soft limit after tightening.

## What the next agent needs

- The runner at `dev/scripts/run-tests-parallel.js` reads `// @parallel true/false` from each test file.
- The bash wrapper at `dev/scripts/test-summary.sh` sets `PYTHONPATH` then delegates to the Node runner.
- The `--concurrency N` flag works for tuning.
- All 36 tests now produce `[PASS]`/`[FAIL]` output lines. The count went from 798 to 833 because the 3 previously-silent tests now report their assertions.
- The `[PASS]`/`[FAIL]` protocol is documented as **L0** in `docs/TESTING_LESSONS.md`.