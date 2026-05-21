# Learnings — Sub-slice 01c.2: Delta-Time Gains for Minimum-Speed and Exit Phases

## What surprised us

1. **Gain time compounds down the straight.** A speed advantage at the apex or exit compounds until the driver lifts off for the next corner. The delta-time trace captures this: if the driver is 429ms behind at the exit but only 364ms behind at the next braking zone, they recovered 65ms on that straight. The heuristic `(ref_speed - driver_speed) / 100` would give only 10ms for our Barcelona t5 example — off by 6.5x.

2. **End of straight = next corner's entry, not next corner's zone start.** The `s_start_m` zone boundary would be wrong because braking zones regularly start 50-100m before the formal zone boundary (same look-back issue from entry detection). Using `find_entry_point()` on the next corner gives the actual lift-off point. For the last corner, measure to the finish line.

3. **The delta-time formula is the same for all phases.** `loss_s = delta_t[straight_end] - delta_t[phase_point]` works for minimum_speed gains, exit gains, and will work for entry gains too. The only difference is which `phase_point` to use (apex, exit distance, or entry distance).

4. **`straight_end` computed once per corner, shared across phases.** Originally computed inside the minimum_speed block and again in the exit block. Refactored to compute once at the top of the loop. This is correct because all phases within the same corner share the same "end of the straight" — it's where the next braking zone starts, which is the same regardless of which phase within the current corner you're measuring from.

5. **`apex_offset_m` sign convention**: `ref_apex - driver_apex`. Positive = driver apexed earlier. For Barcelona t3, driver at 1170m vs reference at 1161m → offset = -9.0 (driver apexed 9m later). This is intuitive: "you apexed late in turn 3."

6. **Delta-time trace final value ≈ `lap_time_delta_s`.** With Barcelona data, `delta_t[-1]` should be close to the actual lap time delta. This provides a natural sanity check.

7. **Speed clamping matters.** Speeds clamped to 1.0 kph in `compute_delta_time_trace()` to avoid division by zero for stopped car / pit lane samples.

8. **`delta_t` must use `lap_time_s`, not speed integration.** Our current `compute_delta_time_trace()` reconstructs cumulative time from speed — this is an approximation. The web UI (`product/web/js/pipeline.js`, `computeDeltaT()`) uses the actual `lap_time_s` column: `dt[i] = (sessionLapTime[i] - refLapTime[i]) * 1000`. We MUST replace our Python version with one that resamples `lap_time_s` onto the 1 m grid, forward-clamps, and computes the difference. This will match the web JS exactly and produce the same delta_t values shown in `product/dist/compare.html`.

## Edge cases handled

- **Last corner on track**: `find_straight_end_after_corner()` returns `track_length - 1` when there's no next corner.
- **Delta-time index out of range**: If `phase_point` or `straight_end` is outside the grid, falls back to the heuristic.
- **Entry gains still use heuristic**: Entry gains need a different algorithm (reference entry detection + distance delta). Not yet implemented.

## What's still heuristic

| Phase | Loss | Gain |
|-------|------|------|
| minimum_speed | `speed_delta / 100.0` | delta-time ✅ |
| exit | `speed_delta / 100.0` | delta-time ✅ |
| entry | `speed_delta / 100.0` | `speed_delta / 100.0` ❌ |

Entry gains need their own algorithm (reference entry detection + delta-time). Losses for all phases need review in 01c.3.