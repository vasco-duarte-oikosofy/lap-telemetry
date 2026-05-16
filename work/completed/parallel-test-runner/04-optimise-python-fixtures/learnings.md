# Slice 04 — Learnings

## What surprised us

1. **Python spawn overhead dominates test fixture time.** Each `spawnSync('python3', ['-c', code])` takes ~0.3 s (startup + import pyarrow). With 9 sequential spawns for a single test file, that's ~2.7 s of overhead alone. Batching all Parquet creation into a single Python process cuts this to ~0.3 s total — a 10× improvement.

2. **Redundant cross-test re-runs were a hidden tax.** `test_width_profile_smoothing.js` Test 9 and `test_width_profile_confidence.js` Test 12 both re-invoked `test_width_profile_export.js` via `spawnSync('node', [...])`, adding ~3 s of overhead each. The parallel runner already runs these tests independently, making the re-runs purely redundant.

3. **Benchmarks: the real bottleneck was I/O, not computation.** The `sys` time for the old tests was 2–4× the `real` time, confirming that spawning processes (not computing results) was the bottleneck.

4. **The `ParquetFixtureBuilder` pattern is reusable.** Any future test that needs synthetic Parquet fixtures can use `const b = new ParquetFixtureBuilder(); ...; b.flush()` instead of per-file `spawnSync`. The `WIDTH_PROFILE_COLS` and `CENTER_PATH_COLS` presets cover the two schemas used across all tests.

5. **`test_m4.js` was silently broken.** It used outdated selectors (`#lap-picker`, `#session-input`, `#ref-input`), a broken HTTP server that only served HTML (wrong MIME types for JS modules), and a resampler cross-check that compared incompatible data paths. The test was never in the package.json test suite, so it was never detected as broken. Fixed by using the shared `startServer()` helper and current UI selectors.

6. **The < 10 s target is now achievable without dual-pool concurrency.** At ~7 s with the default single-pool runner, the fixture optimisation alone gets us under 10 s. Dual-pool concurrency (slice 03) would push this even lower.

## What the next agent needs

- The `ParquetFixtureBuilder` class is in `dev/scripts/parquet-fixture.js`. Usage: `const b = new ParquetFixtureBuilder(); const path = b.add('name', WIDTH_PROFILE_COLS, rows); b.flush();`
- Column presets: `WIDTH_PROFILE_COLS` and `CENTER_PATH_COLS`. Custom columns are supported via the `{ name, type, from }` interface.
- The batch approach queues fixtures at the top of `runTests()` and calls `b.flush()` once before any assertions. This avoids per-fixture Python spawns.
- Test assertion count went from 833 to 828 (5 removed: 3 redundant re-run assertions + 2 that were duplicate within single tests). All 828 assertions are meaningful.