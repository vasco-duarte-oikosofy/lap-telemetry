# Bug: top_gain — measuring gains with the driver's phase distance only

## Problem

The current `compare_laps()` detects phase transitions (entry, exit, minimum speed) using **only the driver's** throttle/brake/speed traces. It then compares `driver_speed[driver_phase_dist]` vs `ref_speed[driver_phase_dist]` — always at the driver's phase distance.

This works for **losses**: "you were slower at the point where YOU lifted / released brakes" is coaching-meaningful.

For **gains** (driver is faster than reference), comparing only at the driver's phase distance is incomplete and can be misleading. A gain means the driver did something *better* — the coaching output should say *what* the driver did better and *by how much*, which requires knowing the reference's phase transitions too.

## Three aspects of the bug

### 1. Entry gains

**Current behavior:** Detects entry at the driver's throttle-lift distance, compares speeds there.  
**Missing:** Where the reference lifted. A gain on entry means the driver lifted *later* (or carried more speed past the reference's lift point). Without the reference's entry distance, we can't say "you lifted 8 m later than reference" — which is the most actionable coaching fact for an entry gain.

**Fix:** Also detect the reference's entry point (throttle lift / speed peak on reference traces). Report both:
- Speed delta at the driver's entry distance.
- Speed delta at the reference's entry distance.
- Distance delta (`reference_entry_m − driver_entry_m`): positive means the driver lifted later.

### 2. Minimum-speed gains

**Current behavior:** Reports `driver_min`, `ref_min`, and the speed delta. Also reports `driver_apex_distance_m` and `reference_apex_distance_m`.  
**Missing:** The distance delta is not surfaced as a named field, and the LLM prompt has no guidance on interpreting gains (only losses). The gain is structurally correct but the coaching message is not formulated — "you carried 5 kph more through turn 4" requires surfacing the delta explicitly.

**Fix:** Add `entry_distance_delta_m` and `apex_offset_m` convenience fields on `CornerLoss` for minimum_speed gains. Update the LLM prompt to interpret gains differently from losses.

### 3. Exit gains

**Current behavior:** Detects exit brake-off and full-throttle on the driver's traces, compares speeds at those distances only.  
**Missing:** Where the reference released brakes / reached full throttle. A gain on exit means the driver released brakes *earlier* or got to full throttle *sooner*. Without the reference's exit distances, we can't say "you released brakes 10 m earlier" — the most actionable coaching fact for an exit gain.

**Fix:** Also detect the reference's exit points (brake release / full throttle on reference traces). Report both:
- Speed delta at the driver's exit distance.
- Speed delta at the reference's exit distance.
- Distance delta (`ref_exit_m − driver_exit_m`): negative means the driver exits earlier = better.

## What this requires

- Resample the **reference** lap's throttle and brake channels onto the same 1 m grid.
- Run `find_entry_point()` and `find_exit_points()` on the reference traces too, producing reference entry/exit distances.
- Add distance-delta fields to `CornerLoss` for gains.
- Update the LLM prompt contract to interpret gains with distance deltas.