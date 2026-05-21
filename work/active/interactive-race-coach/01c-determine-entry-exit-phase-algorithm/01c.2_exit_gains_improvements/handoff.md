# Handoff — Fix: Delta-T calculation uses JS pipeline as single source of truth

## What is on disk now

### New files
- **`dev/scripts/compute_delta_t.mjs`** — Node.js script that imports `computeKeepIndices`, `smoothLapTime`, `resample`, `computeDeltaT`, `smoothDt` from `product/web/js/pipeline.js`. Takes JSON on stdin, outputs resampled grids + delta_t on stdout. ALL channels go through the same computeKeepIndices → resample path as the web UI.
- **`product/python/lap_telemetry/coach/js_pipeline.py`** — Python wrapper that calls the Node.js script via subprocess. Exports `run_js_pipeline()` (returns dict with all grids) and `delta_t_ms_to_seconds()`.
- **`scripts/run_coach_demo.sh`** — One-liner: `bash scripts/run_coach_demo.sh` runs the demo coach.

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** — `compare_laps()` now calls `run_js_pipeline()` instead of doing its own resample+clamp. The JS pipeline handles steps 1-6 (computeKeepIndices, smoothLapTime, resample, forward-clamp, computeDeltaT, smoothDt). Python no longer does any resampling — all grids come from JS.
- **`dev/scripts/test_phase_detection.py`** — 3 new contract tests:
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
4. **`resample_column()` and `compute_delta_time_trace()` retained** in lap_comparator.py for backward compatibility (used by the synthetic unit tests that don't need the JS pipeline).

## How to verify
```bash
bash scripts/run_coach_demo.sh                                    # one-liner demo
python3 dev/scripts/test_phase_detection.py                       # Python tests including JS contract
node dev/scripts/test_coach_lap_comparison.js                      # JS-spawned Python tests
bash scripts/test-summary.sh                                       # full suite
npm run build                                                       # build
```

## Deferred TODOs
- **Entry gains**: Different algorithm needed — delta-time from entry point to end of straight, plus reference entry detection for distance deltas.
- **Exit reference detection**: `exit_distance_delta_m` comparing driver vs reference exit points.
- **Losses algorithm review (01c.3)**: Evaluate whether losses should also use delta-time.
- **Potential optimization**: Cache the JS pipeline result per lap pair to avoid redundant subprocess calls if compare_laps is called repeatedly for the same data.