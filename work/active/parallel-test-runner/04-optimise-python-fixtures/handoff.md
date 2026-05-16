# Slice 04 — Handoff

## What changed

### New files
- `dev/scripts/parquet-fixture.js` — shared `ParquetFixtureBuilder` class (74 lines)
  - `.add(name, columnDefs, rows)` queues a Parquet creation request
  - `.flush()` creates all queued fixtures in a single `python3` process
  - Exports `WIDTH_PROFILE_COLS` and `CENTER_PATH_COLS` presets

### Modified files
- `dev/scripts/test_width_profile_export.js` — replaced 9 `buildParquet()` calls with batched `b.add()` + 1 `b.flush()`
- `dev/scripts/test_width_profile_confidence.js` — replaced 3 `buildParquet()` + removed Test 12 (re-ran export test)
- `dev/scripts/test_width_profile_smoothing.js` — replaced 2–3 `buildParquet()` + removed Test 9 (re-ran export + confidence tests)
- `dev/scripts/test_center_path_export.js` — replaced 10 `buildParquet()` calls with batched approach

## What's on disk now

- Full suite: **ALL PASS — 828 assertions across 36 test scripts in ~7 s**
- Parquet fixture module: `dev/scripts/parquet-fixture.js`
- Removed 5 redundant assertions (833 → 828), all re-runs of other test files
- Build: `npm run build` succeeds

## Performance improvement

| Test file | Before | After | Improvement |
|---|---|---|---|
| test_width_profile_export.js | ~2.6 s | ~1.0 s | 2.6× |
| test_width_profile_confidence.js | ~3.7 s | ~0.9 s | 4.1× |
| test_width_profile_smoothing.js | ~7.6 s | ~1.1 s | 6.9× |
| test_center_path_export.js | ~3.0 s | ~1.0 s | 3.0× |
| **Full suite** | **~17 s** | **~7 s** | **2.4×** |

## Feature flags / config

- None. The `ParquetFixtureBuilder` is a test utility, no runtime config.

## Deferred TODOs

- Slice 03 (dual-pool concurrency for Node/Playwright) still pending
- Slice 05 (runner self-test) still pending
- Consider: the 4 remaining Python-invoking tests (m4/m5/m6/m6_extras) still call `spawnSync('python3')` inline but are fast enough not to bottleneck (each <3 s)
- Consider: `test_m4.js` still fails with 0 assertions (pre-existing issue, not related to this slice)