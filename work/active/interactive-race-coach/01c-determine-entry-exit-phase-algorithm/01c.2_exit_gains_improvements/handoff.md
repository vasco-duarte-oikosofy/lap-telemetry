# Handoff — Sub-slice 01c.2: Apex Minimum-Speed Gain Algorithm

## What is on disk now

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** — Main algorithm file. Changes:
  - `compute_delta_time_trace()` — new function that builds a cumulative time delta trace at 1 m resolution. `delta_t[s] = driver_cumtime[s] - ref_cumtime[s]`. Positive = driver behind, negative = driver ahead.
  - `find_straight_end_after_corner()` — new function that finds the end of the straight after a given corner (entry of next corner, or end of lap for last corner).
  - `CornerLoss.apex_offset_m` — new field: `ref_apex_m - driver_apex_m`. Positive = driver apexed earlier. Populated for all minimum_speed phases (both losses and gains).
  - `compare_laps()` — now computes `delta_t` trace and uses it for minimum_speed gains. For gains (`speed_delta < 0`), `loss_s = delta_t[straight_end] - delta_t[apex]` (real integrated time). For losses (`speed_delta > 0`), `loss_s = speed_delta / 100.0` unchanged. Passes `corner_idx` to the loop for `find_straight_end_after_corner()`.
  - `LapComparisonFacts.to_dict()` — includes `apex_offset_m` when present.

### Updated files
- **`dev/scripts/test_phase_detection.py`** — Added 10 new test functions:
  - `test_delta_time_trace_basic` — slower driver → positive trace
  - `test_delta_time_trace_faster_driver` — faster driver → negative trace
  - `test_delta_time_trace_equal_speeds` — equal speeds → near-zero trace
  - `test_delta_time_trace_matches_lap_time` — final value ≈ lap time delta
  - `test_find_straight_end_middle_corner` — end of straight = next corner's entry
  - `test_find_straight_end_last_corner` — end of straight = end of lap for last corner
  - `test_minimum_speed_gain_uses_delta_time` — synthetic gain scenario with delta-time verification
  - `test_minimum_speed_loss_unchanged` — loss still uses heuristic
  - `test_apex_offset_in_comparison` — Barcelona fixture has `apex_offset_m` on minimum_speed phases
  - `test_minimum_speed_gain_negative_loss_s` — all gains have negative `loss_s`

### Spec files
- `work/active/interactive-race-coach/01c-determine-entry-exit-phase-algorithm/01c.2_exit_gains_improvements/apex_min_speed_gain_algorithm.md` — full spec
- `work/active/interactive-race-coach/01c-determine-entry-exit-phase-algorithm/01c.2_exit_gains_improvements/entry_gain_algorithm.md` — spec (not yet implemented)
- `work/active/interactive-race-coach/01c-determine-entry-exit-phase-algorithm/01c.2_exit_gains_improvements/exit_gain_algorithm.md` — spec (not yet implemented)
- `work/active/interactive-race-coach/01c-determine-entry-exit-phase-algorithm/top_gain_exit_bug.md` — bug description covering all three aspects
- `work/active/interactive-race-coach/01c-determine-entry-exit-phase-algorithm/01c.3_losses_gains_algorithm_review/prompt.md` — future review slice for losses algorithm

## Key design decisions

1. **Losses unchanged**: Minimum-speed losses still use `loss_s = speed_delta / 100.0`. Only gains use real delta-time.
2. **Gain formula**: `loss_s = delta_t[straight_end] - delta_t[apex]`. Negative = driver gained time (further ahead at end of straight than at apex).
3. **End of straight**: Entry of next corner (throttle lift < 0.9 or brake > 0.05), or `track_length - 1` for the last corner.
4. **Delta-time trace**: Computed once per lap, reused for all corners. `delta_t[s] = driver_cumtime - ref_cumtime`. Speeds clamped to 1.0 kph minimum to avoid division by zero.
5. **`apex_offset_m`**: Added to all minimum_speed phases (losses and gains). `ref_apex - driver_apex`. Positive = driver apexed earlier.
6. **Mixed units**: Minimum-speed gains are now in real seconds. All other phases (entry, exit) still use the heuristic. This is documented in the spec as a known inconsistency, to be resolved in the review slice (01c.3).

## How to verify
```bash
cd product/python && python3 demo_coach_slice01.py --verbose
```
```bash
python3 dev/scripts/test_phase_detection.py
```

## Deferred TODOs
- Entry gain algorithm (reference entry detection, `entry_distance_delta_m`, delta-time for entry gains)
- Exit gain algorithm (reference exit detection, `exit_distance_delta_m`, delta-time for exit gains)
- Losses algorithm review (01c.3) — evaluate whether losses should also use delta-time
- Mixed units resolution — once all phases use delta-time, the `loss_s` semantics will be consistent