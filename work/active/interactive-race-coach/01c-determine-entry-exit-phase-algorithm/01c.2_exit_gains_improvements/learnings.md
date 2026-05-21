# Learnings — Sub-slice 01c.2: Apex Minimum-Speed Gain Algorithm

## What surprised us

1. **Gain time compounds down the straight.** A speed advantage at the apex doesn't just measure at the apex — it compounds until the driver lifts off for the next corner. The delta-time trace (`delta_t[straight_end] - delta_t[apex]`) captures this correctly: if the driver is 0.15s ahead at the apex and 0.25s ahead at the next braking zone, the gain from apex to end of straight is 0.10s.

2. **End of straight = next corner's entry, not next corner's zone start.** The `s_start_m` zone boundary would be 50-100m off for many corners (the same look-back issue from entry detection). Using `find_entry_point()` on the next corner gives the actual lift-off point. For the last corner, measure to the finish line.

3. **Losses and gains now use different units for minimum_speed.** Gains are in real integrated seconds; losses are in heuristic `speed_delta/100` "seconds." This is intentional and documented. The 01c.3 review slice should evaluate unifying them.

4. **`apex_offset_m` sign convention.** `ref_apex - driver_apex`: positive means driver apexed earlier (their minimum is at a shorter distance). Negative means driver apexed later. For Barcelona t3, the driver apexed at 1170m while the reference was at 1161m → offset = -9.0 (driver is 9m late). This matches the coaching message: "you apexed 9m late in turn 3."

5. **Delta-time trace final value approximates `lap_time_delta_s`.** With Barcelona data, `delta_t[-1]` should be close to the actual lap time delta. This provides a natural sanity check for the trace computation.

6. **Speed clamping matters.** The delta-time trace clamps speeds to 1.0 kph minimum. Without this, a zero-speed sample (stopped car, pit lane) would cause division by zero. The clamp adds a negligible time error at very low speeds.

## Edge cases handled

- **Last corner on track**: `find_straight_end_after_corner()` returns `track_length - 1` when there's no next corner.
- **Delta-time index out of range**: If `driver_apex_m` or `straight_end` is outside the grid, falls back to the heuristic `speed_delta / 100.0`.
- **Zero speed**: Clamped to 1.0 kph in `compute_delta_time_trace()`.

## Dependencies for future slices

- `compute_delta_time_trace()` and `find_straight_end_after_corner()` are shared infrastructure that entry and exit gain algorithms will reuse.
- The delta-time trace should eventually be used for all phase gains (entry, exit, minimum_speed), not just minimum_speed.