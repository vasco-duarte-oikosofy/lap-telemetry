# Handoff — 01c.2 Exit gains improvements

Three sub-slices were delivered within 01c.2:

1. **Fix delta-T calculation** — JS pipeline as single source of truth
2. **Apex/min-speed gain algorithm** — delta-t apex→straight_end
3. **Entry gain algorithm** — delta-t entry→apex

---

## What is on disk now

### New files
- **`dev/scripts/compute_delta_t.mjs`** (138 lines) — Node.js script that imports `computeKeepIndices`, `smoothLapTime`, `resample`, `computeDeltaT`, `smoothDt` from `product/web/js/pipeline.js`. Takes JSON on stdin, outputs resampled grids + delta_t on stdout. ALL channels go through the same computeKeepIndices → resample path as the web UI.
- **`product/python/lap_telemetry/coach/js_pipeline.py`** (99 lines) — Python wrapper that calls the Node.js script via subprocess. Exports `run_js_pipeline()` (returns dict with all grids) and `delta_t_ms_to_seconds()`.
- **`product/python/lap_telemetry/coach/facts.py`** (88 lines) — Extracted dataclasses: `PhaseDetectionThresholds`, `CornerLoss`, `LapComparisonFacts` (with `to_dict()`).
- **`product/python/lap_telemetry/coach/resample.py`** (61 lines) — Python-only `resample_column()` and `compute_delta_time_trace()`. Used by synthetic unit tests that don't need the JS pipeline. Also used by `generate_track_coaching_model_from_reference.py`.
- **`scripts/run_coach_demo.sh`** (6 lines) — One-liner: `bash scripts/run_coach_demo.sh` runs the demo coach.

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** (436 lines, was 626) — `compare_laps()` calls `run_js_pipeline()` for all resampling/delta_t. Entry/exit/minimum_speed gains all use real delta-time within their phase boundaries. Losses use speed_delta/100.0 heuristic. `gain_end_distance_m` field populated for gains (apex for entry, straight_end for minimum_speed and exit).
- **`dev/scripts/test_phase_detection.py`** (959 lines) — JS pipeline contract tests, gain algorithm tests (synthetic + fixture), entry gain delta-t tests.

---

## Gain algorithm summary (all three phases)

| Phase   | Gain signal         | Measurement window       | gain_end_distance_m |
|---------|--------------------|--------------------------|---------------------|
| entry   | entry_delta < 0    | entry_point → apex        | apex                |
| minimum_speed | speed_delta < 0 | apex → straight_end       | straight_end        |
| exit    | exit_delta < 0     | exit_point → straight_end  | straight_end        |

Losses in all three phases still use `speed_delta / 100.0` heuristic.

---

## Barcelona output: before → after (all sub-slices combined)

### Delta-t accuracy (fix_delta_t sub-slice)
| Metric | Before (Python partial) | After (JS pipeline) |
|--------|----------------------|---------------------|
| delta_t[2158] | +423.5 ms | +436.4 ms ✅ (matches web UI) |
| delta_t[2439] | +355.1 ms | +331.3 ms ✅ (matches web UI) |

### Entry gains (swapped fixture, entry_gain sub-slice)
| Corner | Old heuristic (ms) | New delta-t (ms) | Change |
|--------|------------------:|------------------:|--------|
| t1     | -84.5            | -155.8            | 84% larger |
| t7     | -103.6           | -155.0            | 50% larger |
| t4     | -33.4            | -81.0             | 143% larger |
| t11    | -33.6            | -66.8             | 99% larger |
| t8     | -46.1            | -57.7             | 25% larger |
| t9     | -14.9            | -52.2             | 250% larger |
| t10    | -21.0            | -29.0             | 38% larger |
| t2     | -17.4            | +8.1 (loss)       | sign flip (chicane) |
| t3     | -17.4            | +36.5 (loss)      | sign flip (chicane) |

---

## Key design decisions

1. **Single source of truth: product/web/js/pipeline.js.** Both the web UI and Python coaching engine run the same JavaScript code. No drift is possible by design.
2. **All channels through JS pipeline.** Speed, throttle, brake all go through computeKeepIndices filtering before resampling — not just lap_time_s.
3. **Phase boundaries avoid double-counting.** Entry gains stop at apex, minimum_speed and exit gains stop at straight_end. No overlap.
4. **Chicane sign flip is correct behaviour.** Shared entry points (t2/t3 at 909 m) measure different entry→apex windows. The delta-t can reveal a loss (driver gave back time in the chicane) even when the speed at the entry point suggested a gain.
5. **Fallback heuristic for out-of-range indices.** If delta_t indices are out of bounds or entry_idx >= apex_idx, falls back to speed_delta/100.0.

---

## How to verify
```bash
bash scripts/run_coach_demo.sh                                    # one-liner demo
python3 dev/scripts/test_phase_detection.py                       # Python tests including JS contract
node dev/scripts/test_coach_lap_comparison.js                      # JS-spawned Python tests
bash scripts/test-summary.sh                                       # full suite
npm run build                                                       # build
```

---

## Known issues

- **`test_phase_detection.py` is 959 lines** — far exceeds the 437 line hard ceiling. Split tracked in 01c.3.
- **`lap_comparator.py` is 436 lines** — 1 line of margin under the 437 ceiling. Included in the 01c.3 prompt.

## Deferred TODOs
- **`entry_distance_delta_m`**: Distance comparison of driver vs reference entry points ("you lifted 8 m later than reference"). Orthogonal to delta-time fix. Deferred alongside `exit_distance_delta_m`.
- **`exit_distance_delta_m`**: Comparing driver vs reference exit points for distance deltas.
- **Losses algorithm review**: Evaluate whether entry/exit losses should also use delta-t. Currently losses use speed_delta/100.0 heuristic for both entry and exit.
- **Split oversized test file**: See `01c.3_fix_oversized_modules_to_keep_to_max_437_lines/prompt.md`.