# Slice 04 — Optimise Python-invoking test fixtures

## Goal

Reduce the wall-time of 4 Python-invoking Node test scripts from ~17 s sequential to under 5 s total by batching Parquet fixture creation into single Python invocations and removing redundant re-run tests. Combined with dual-pool concurrency (slice 03), this makes the < 10 s spec target achievable.

## Context

The 4 slowest Node tests each call `spawnSync('python3', ...)` multiple times to create synthetic Parquet fixtures. Benchmarks show:

- 10 sequential Python spawns: ~3 s
- 1 batched spawn (10 files): ~0.3 s
- That's a 10× improvement per test file

The tests are:
- `test_width_profile_export.js` — 9 builds, 2.6 s
- `test_width_profile_confidence.js` — 3 builds + 1 re-run, 3.7 s
- `test_width_profile_smoothing.js` — 2–3 builds + 2 re-runs, 7.6 s
- `test_center_path_export.js` — 9 builds + 1 re-run, 3.0 s

Additionally, `test_width_profile_smoothing.js` Tests 9–10 and `test_width_profile_confidence.js` Test 12 re-invoke other test scripts via `spawnSync('node', [...])`, adding redundant overhead — those other tests are already run independently by the test suite.

## Steps

1. **Create `dev/scripts/parquet-fixture.js`** — shared module with `ParquetFixtureBuilder`:
   - `.add(name, columnDefs, rows)` — queues a Parquet creation request, returns the output path
   - `.flush()` — creates all queued Parquet files in a single `python3` process
   - Supports the two schemas used across the 4 tests (width-profile columns and center-path columns)
   - Line count: under 80 lines

2. **Refactor `test_width_profile_export.js`** — replace all `buildParquet()` calls with `builder.add()` / `builder.flush()`. No change to assertion logic.

3. **Refactor `test_width_profile_confidence.js`** — same treatment. Remove Test 12 (re-runs `test_width_profile_export.js`), since the suite already runs that script independently.

4. **Refactor `test_width_profile_smoothing.js`** — same treatment. Remove Test 9 (re-runs `test_width_profile_export.js` and `test_width_profile_confidence.js`), since those are already run independently. Change Test 10 to use the builder if it creates Parquet files.

5. **Refactor `test_center_path_export.js`** — same treatment. Remove Test 11 (re-runs width profile export script).

6. **Run `bash scripts/test-summary.sh`** — all 36 tests must pass; assertion count must remain 833 (minus only the removed re-run assertions, which duplicate what the suite already tests independently).

7. **Commit.**

## Acceptance

- `test_width_profile_export.js` wall-time ≈ 0.5 s (down from 2.6 s)
- `test_width_profile_confidence.js` wall-time ≈ 1.0 s (down from 3.7 s)
- `test_width_profile_smoothing.js` wall-time ≈ 2.0 s (down from 7.6 s), mainly due to real-data Spa session test
- `test_center_path_export.js` wall-time ≈ 0.5 s (down from 3.0 s)
- Full suite: ALL PASS, assertion count preserved (minus removed re-run assertions)
- `parquet-fixture.js` under 80 lines
- No new runtime dependencies

## Non-goals

- Do not change the parallel runner (slice 03 scope).
- Do not add Parquet-write capability to `hyparquet` or any new npm package.
- Do not change individual test assertion logic — only fixture creation and redundant re-runs.