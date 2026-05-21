# Handoff — Sub-slice 01c.2: Delta-Time Gains for Minimum-Speed and Exit Phases

## What is on disk now

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** — Main algorithm file. Changes:
  - `compute_delta_time_trace()` — builds cumulative time delta trace at 1 m resolution. `delta_t[s] = driver_cumtime[s] - ref_cumtime[s]`. Positive = driver behind, negative = driver ahead.
  - `find_straight_end_after_corner()` — finds the end of the straight after a given corner (entry of next corner, or end of lap for last corner).
  - `CornerLoss.apex_offset_m` — new field: `ref_apex_m - driver_apex_m`. Positive = driver apexed earlier. Populated for all minimum_speed phases.
  - `compare_laps()` — now uses delta-time for **minimum-speed and exit gains**. For gains (`speed_delta < 0`), `loss_s = delta_t[straight_end] - delta_t[phase_point]` (real integrated time). For losses (`speed_delta > 0`), `loss_s = speed_delta / 100.0` unchanged. `straight_end` is computed once per corner at the top of the loop.
  - `LapComparisonFacts.to_dict()` — includes `apex_offset_m` when present.

### Barcelona output (t5 exit gain)
- Before: `loss_s: -0.01` (heuristic: `(91-92)/100`)
- After: `loss_s: -0.065` (real time: delta_t[2439] - delta_t[2158] = 0.364 - 0.429 = -0.065s)
- The driver recovered 65ms from the t5 exit to the next braking zone.

### Updated files
- **`dev/scripts/test_phase_detection.py`** — 10 new test functions covering delta-time trace, straight-end detection, gain calculation with delta-time, and fixture verification.

### Spec files
- `01c.2_exit_gains_improvements/apex_min_speed_gain_algorithm.md` — implemented
- `01c.2_exit_gains_improvements/entry_gain_algorithm.md` — spec (not yet implemented; entry gains need a different algorithm)
- `01c.2_exit_gains_improvements/exit_gain_algorithm.md` — partially implemented (delta-time gain, but not yet reference exit detection or distance deltas)
- `01c.3_losses_gains_algorithm_review/prompt.md` — future review for losses algorithm and entry gains

## Key design decisions

1. **Losses unchanged for all phases**: Both minimum-speed and exit losses still use `loss_s = speed_delta / 100.0`. Only gains use real delta-time.
2. **Gain formula (same for minimum_speed and exit)**: `loss_s = delta_t[straight_end] - delta_t[phase_point]`. Negative = driver gained time.
3. **End of straight**: Computed once per corner via `find_straight_end_after_corner()`. Uses driver's throttle/brake traces to find the next corner's entry point. For the last corner, returns `track_length - 1`.
4. **Delta-time trace**: Computed once per lap, reused for all corners. Speeds clamped to 1.0 kph minimum.
5. **`apex_offset_m`**: On all minimum_speed phases. `ref_apex - driver_apex`. Positive = driver apexed earlier.
6. **Entry gains still use heuristic**: Entry gain algorithm is different (needs reference entry detection) and is deferred to a future sub-slice.

## How to verify
```bash
cd product/python && python3 demo_coach_slice01.py --verbose
python3 dev/scripts/test_phase_detection.py
bash scripts/test-summary.sh
npm run build
```

## Known issue: delta_t calculation must match web JS

Our current `compute_delta_time_trace()` reconstructs cumulative time from speed: `time_per_meter = 1 / (speed_kph / 3.6)`, summed over distance. This is an **approximation** that may differ from the actual recorded `lap_time_s`.

The web UI (`product/web/js/pipeline.js`, `computeDeltaT()`) uses `lap_time_s` directly:
```js
dt[i] = (sessionLapTime[i] - refLapTime[i]) * 1000;
```

We MUST replace `compute_delta_time_trace()` with a version that:
1. Resamples both laps' `lap_time_s` onto the 1 m grid using `resample_column()`
2. Forward-clamps so `lap_time_s` is non-decreasing (handles LMU's ~5 Hz update rate)
3. Computes `delta_t[i] = driver_lap_time[i] - ref_lap_time[i]`

This will match the web JS exactly and give the same delta_t values shown in `product/dist/compare.html`.

## Deferred TODOs
- **Entry gains**: Different algorithm needed — delta-time from entry point to end of straight, plus reference entry detection for distance deltas.
- **Exit reference detection**: `exit_distance_delta_m` comparing driver vs reference exit points (spec exists but not yet implemented).
- **Losses algorithm review (01c.3)**: Evaluate whether losses should also use delta-time, and address entry gain algorithm.
- **Mixed units**: Minimum-speed and exit gains are in real seconds; entry gains and all losses still use the heuristic.