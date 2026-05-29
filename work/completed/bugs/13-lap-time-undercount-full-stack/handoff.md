# Handoff — Bug 13

Implemented in `58f9f8b`.

## What changed

- Added `product/python/lap_telemetry/parquet_utils.py` with shared `build_segments()` and `authoritative_duration()` helpers.
- `lap-telemetry summary` now uses scorer-based durations from the next segment when available.
- `coach/lap_comparator.py` keeps the full session table so `lap_number` comparisons can read the following segment for authoritative driver duration.
- Extracted reference lap comparison uses opt-in same-segment scorer fallback.
- `product/web/js/pipeline.js` accepts optional `scoring_last_lap_time_s` in `annotateSegments()` and corrects `seg.duration` before fastest-lap selection.
- `product/web/js/ui.js` loads `scoring_last_lap_time_s`; `pickers.js` displays `seg.duration` instead of recomputing raw `max(lap_time_s)`.
- Older sessions without `scoring_last_lap_time_s` fall back to existing `max(lap_time_s)` behavior.
- Moved legacy Python bug tests from root `tests/` to `dev/scripts/`, added `dev/scripts/test_bug_python_regressions.js`, and documented this in `AGENTS.md`.

## Validation

- `bash scripts/test-summary.sh dev/scripts/test_bug_python_regressions.js` ✅
- `bash scripts/test-summary.sh dev/scripts/test_bug13_authoritative_duration.js` ✅
- `bash scripts/test-summary.sh --feature interactive-race-coach` ✅
- `bash scripts/test-summary.sh --pw` ✅
- `npm run build` ✅ (`product/dist/compare.html` rebuilt)

## Status

Bug 13 is fixed in code and tests. Per repo rules, the bug folder remains under `work/active/bugs/` until live/user confirmation before moving to completed.
