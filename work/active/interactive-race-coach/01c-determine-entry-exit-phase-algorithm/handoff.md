# Handoff — Slice 01c: Determine Entry/Exit Phase Algorithm

## Status: ✅ Complete

All acceptance criteria from `prompt.md` Definition of Done are met. Sub-slices 01c.2 and 01c.3 also delivered. Only 01c.4 (decision document, not implementation) remains as a follow-up.

## What is on disk now

### New files
- **`product/python/lap_telemetry/coach/entry_detection.py`** (78 lines) — `find_entry_point`, `find_brake_point`
- **`product/python/lap_telemetry/coach/exit_detection.py`** (65 lines) — `find_exit_points`
- **`product/python/lap_telemetry/coach/js_pipeline.py`** (99 lines) — Python wrapper calling Node.js telemetry pipeline
- **`product/python/lap_telemetry/coach/facts.py`** (88 lines) — `PhaseDetectionThresholds`, `CornerLoss`, `LapComparisonFacts`
- **`product/python/lap_telemetry/coach/resample.py`** (61 lines) — Python-only `resample_column`, `compute_delta_time_trace`
- **`dev/scripts/compute_delta_t.mjs`** (138 lines) — Node.js script importing pipeline.js
- **`scripts/run_coach_demo.sh`** (6 lines) — one-liner demo
- **`dev/scripts/test_delta_time_gains.py`** (375 lines) — delta-time and gain tests
- **`dev/scripts/test_js_pipeline_contract.py`** (124 lines) — JS pipeline contract tests
- **Node.js wrappers** for all three Python test files (33 lines each)

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** (241 lines, was 626) — Main comparison engine. Imports from entry_detection, exit_detection. All gains use real delta-time; losses use `speed_delta / 100.0` heuristic.
- **`dev/scripts/test_phase_detection.py`** (381 lines, was 959) — Phase detection tests. Split from monolith.

## Gain algorithm summary (all three phases use real delta-time)

| Phase | Gain signal | Measurement window | gain_end_distance_m |
|-------|-------------|-------------------|---------------------|
| entry | entry_delta < 0 | entry_point → apex | apex |
| minimum_speed | speed_delta < 0 | apex → straight_end | straight_end |
| exit | exit_delta < 0 | exit_point → straight_end | straight_end |

Losses in all three phases still use `speed_delta / 100.0` heuristic.

## Key design decisions

1. **JS pipeline as single source of truth** — `product/web/js/pipeline.js` runs in both web UI and Python coaching engine. No drift possible by design.
2. **Phase boundaries avoid double-counting** — entry gains stop at apex, minimum_speed and exit gains stop at straight_end.
3. **Chicane sign flip is correct** — shared entry points (t2/t3) measure different windows; delta_t can reveal a loss at entry even when speed suggested a gain.

## How to verify
```bash
bash scripts/test-summary.sh --feature interactive-race-coach        # feature tests
bash scripts/test-summary.sh                                         # full suite
npm run build                                                         # build
```

## Deferred: 01c.4

A decision document on whether to extend delta-time to losses and whether to implement entry/exit distance deltas. See `01c.4_losses_gains_algorithm_review/prompt.md`.