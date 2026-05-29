# Handoff — Bug 16

Implemented pending live confirmation.

## What changed

- `product/python/lap_telemetry/coach/lap_comparator.py`
  - Added `_SLOW_LAP_RATIO_THRESHOLD = 1.15`.
  - After distance coverage and reference load, compares authoritative driver/reference durations before running the JS pipeline.
  - Raises `PartialLapError` with a duration/pitstop/safety-car message when driver duration is more than 115% of reference.
- `product/web/js/pipeline.js`
  - Added matching `SLOW_LAP_RATIO_THRESHOLD = 1.15`.
  - Added `isSlowLapComparedToReference()`.
  - `annotateSegments()` marks full-distance laps more than 115% of median clean-lap duration as `partial`.
- `dev/scripts/test_bug16_slow_lap_guard.js`
  - Covers the real lap-13 repro file, synthetic 115% pass, 116% reject, and JS slow-lap partial marking.
- `package.json`
  - Adds the bug-16 regression to the main suite and `interactive-race-coach` feature suite.
- `product/dist/compare.html`
  - Rebuilt with the JS-side slow-lap marking.

## Validation

- `bash scripts/test-summary.sh dev/scripts/test_bug16_slow_lap_guard.js` ✅
- `bash scripts/test-summary.sh dev/scripts/test_m5.js` ✅
- `bash scripts/test-summary.sh dev/scripts/test_m6.js` ✅
- `bash scripts/test-summary.sh --feature interactive-race-coach` ✅
- `npm run build` ✅
- `bash scripts/test-summary.sh --pw` ✅

## Status

Bug 16 is fixed in code and tests. Per repo rules, keep this folder under `work/active/bugs/` until the user confirms a live/manual test, then move it to `work/completed/bugs/` and update the PLAN row with the final commit hash.
