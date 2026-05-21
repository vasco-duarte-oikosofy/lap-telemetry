# Handoff — Fix: Delta-T calculation uses JS pipeline as single source of truth

## What is on disk now

### New files
- **`dev/scripts/compute_delta_t.mjs`** (138 lines) — Node.js script that imports `computeKeepIndices`, `smoothLapTime`, `resample`, `computeDeltaT`, `smoothDt` from `product/web/js/pipeline.js`. Takes JSON on stdin, outputs resampled grids + delta_t on stdout. ALL channels go through the same computeKeepIndices → resample path as the web UI.
- **`product/python/lap_telemetry/coach/js_pipeline.py`** (99 lines) — Python wrapper that calls the Node.js script via subprocess. Exports `run_js_pipeline()` (returns dict with all grids) and `delta_t_ms_to_seconds()`.
- **`product/python/lap_telemetry/coach/facts.py`** (88 lines) — Extracted dataclasses: `PhaseDetectionThresholds`, `CornerLoss`, `LapComparisonFacts` (with `to_dict()`).
- **`product/python/lap_telemetry/coach/resample.py`** (61 lines) — Python-only `resample_column()` and `compute_delta_time_trace()`. Used by synthetic unit tests that don't need the JS pipeline. Also used by `generate_track_coaching_model_from_reference.py`.
- **`scripts/run_coach_demo.sh`** (6 lines) — One-liner: `bash scripts/run_coach_demo.sh` runs the demo coach.

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** (433 lines, was 626) — `compare_laps()` now calls `run_js_pipeline()` instead of doing its own resample+clamp. The JS pipeline handles steps 1-6 (computeKeepIndices, smoothLapTime, resample, forward-clamp, computeDeltaT, smoothDt). Python no longer does any resampling — all grids come from JS. Legacy functions (compute_corner_entry_loss, compute_corner_exit_loss) removed. Dataclasses moved to facts.py.
- **`dev/scripts/test_phase_detection.py`** (817 lines) — 3 new contract tests added:
  - `test_js_pipeline_delta_t_matches_web_ui()` — verifies delta_t[2158]=436 ms, delta_t[2439]=331 ms, delta_t[-1]=1155 ms
  - `test_js_pipeline_speed_matches_web_ui()` — verifies speed grids and array alignment
  - `test_js_pipeline_smooth_dt_reduces_jitter()` — verifies smoothDt attenuates jitter

### Barcelona output change
| Metric | Before (Python partial) | After (JS pipeline) |
|--------|----------------------|---------------------|
| delta_t[2158] | +423.5 ms | +436.4 ms ✅ (matches web UI) |
| delta_t[2439] | +355.1 ms | +331.3 ms ✅ (matches web UI) |
| t5 exit gain | -68 ms | -105 ms |
| t8 min_speed loss | 0.318 (top loss) | 0.106 (3rd loss) |

The gain/loss numbers changed because the delta_t values are now accurate. Previously, the Python partial pipeline was missing boundary-artifact filtering, plateau smoothing, and jitter attenuation — all of which affected the delta_t trace shape.

## Key design decisions

1. **Single source of truth: product/web/js/pipeline.js.** Both the web UI and Python coaching engine run the same JavaScript code. No drift is possible by design.
2. **All channels through JS pipeline.** Speed, throttle, brake all go through computeKeepIndices filtering before resampling — not just lap_time_s.
3. **Node.js runtime dependency.** Python coaching pipeline requires Node.js (already present for the build). IPC via stdin/stdout JSON.
4. **`resample_column()` and `compute_delta_time_trace()` retained** in resample.py for backward compatibility (used by synthetic unit tests and generate_track_coaching_model_from_reference.py).

## How to verify
```bash
bash scripts/run_coach_demo.sh                                    # one-liner demo
python3 dev/scripts/test_phase_detection.py                       # Python tests including JS contract
node dev/scripts/test_coach_lap_comparison.js                      # JS-spawned Python tests
bash scripts/test-summary.sh                                       # full suite
npm run build                                                       # build
```

## Known issues

- **`test_phase_detection.py` is 817 lines** — exceeds the 437 line hard ceiling. A prompt for splitting it has been created at `01c.3_fix_oversized_modules_to_keep_to_max_437_lines/prompt.md`.
- **`lap_comparator.py` is 433 lines** — only 4 lines of margin under the 437 ceiling. Included in the 01c.3 prompt.

## Deferred TODOs
- **Entry gains**: Different algorithm needed — delta-time from entry point to end of straight, plus reference entry detection for distance deltas.
- **Exit reference detection**: `exit_distance_delta_m` comparing driver vs reference exit points.
- **Losses algorithm review (01c.3)**: Evaluate whether losses should also use delta-time.
- **Split oversized test file**: See `01c.3_fix_oversized_modules_to_keep_to_max_437_lines/prompt.md`.