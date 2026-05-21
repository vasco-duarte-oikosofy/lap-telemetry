# Exit gain algorithm

## Current behavior

`find_exit_points()` uses **only the driver's** brake/throttle traces:

1. Walk forward from `apex_s_m` toward `s_end_m`.
2. Detect brake release (`exit_brake`) and/or full throttle (`exit_throttle`) on the driver's traces.
3. Compare: `driver_speed[driver_exit_m]` vs `ref_speed[driver_exit_m]`.
4. If `exit_delta = ref_exit - driver_exit > 1.0` → loss; `< -1.0` → gain.

For a **loss**, this is coaching-meaningful: "at the point where you released brakes, you were 3 kph slower than reference."

For a **gain**, it's incomplete: the driver exited earlier (released brakes sooner, got to power sooner) but we can't say *how much* earlier without knowing the reference's exit point. The most actionable exit-gain fact is the **distance delta**: "you released brakes 10 m earlier than reference."

## What's needed

### Detect the reference's exit points

Run `find_exit_points()` on the **reference lap's** resampled brake/throttle traces. This produces reference exit distances:
- `ref_exit_brake_m` — where the reference released brakes.
- `ref_exit_throttle_m` — where the reference reached full throttle.

### New fields on `CornerLoss` for exit gains

```python
@dataclass
class CornerLoss:
    # ... existing fields ...
    exit_distance_delta_m: float | None = None  # ref_exit - driver_exit; negative = driver exits earlier = gain
    reference_phase_distance_m: float | None = None  # ref's phase distance (shared with entry)
```

For exit phases:
- `exit_distance_delta_m = reference_exit_m - driver_exit_m`
  - Negative → driver exited earlier than reference (released brakes / reached full throttle sooner) = gain.
  - Positive → driver exited later than reference = loss.
- `reference_phase_distance_m = reference_exit_m` — where the reference's corresponding exit was detected.

### Speed comparison for exit gains

Keep existing speed comparison at `phase_distance_m` (= driver's exit distance):
- `driver_value = driver_speed[driver_exit_m]`
- `reference_value = ref_speed[driver_exit_m]`
- `loss_s = (reference_value - driver_value) / 100.0`

The reference's exit distance is available via `reference_phase_distance_m` for distance-delta coaching. The primary speed comparison stays at the driver's exit distance for consistency.

### Merge logic for reference exit points

The same merge logic that applies to driver exit points applies to reference exit points:

1. Detect `ref_exit_brake_s` and `ref_exit_throttle_s` independently.
2. If both detected and within merge tolerance → single `ref_exit` at midpoint.
3. If both detected and beyond merge tolerance → two distinct reference exit points.
4. If only one channel → single `ref_exit` at that distance.
5. If neither → `ref_exit = s_end_m`.

When the driver has a merged `exit` but the reference has separate `exit_brake` / `exit_throttle` (or vice versa), the distance delta uses the closest matching pair. Priority:
- `exit_brake` driver ↔ `exit_brake` reference
- `exit_throttle` driver ↔ `exit_throttle` reference
- `exit` driver ↔ `exit` reference (when both are merged)
- If one is merged and the other is split: use the closest phase. `reference_phase_distance_m` reports whichever reference distance matched.

### Exit distance delta sign convention

```
exit_distance_delta_m = reference_exit_m - driver_exit_m
```

| Scenario | delta | Meaning |
|----------|-------|---------|
| Driver exits earlier | negative | "you released brakes 10 m earlier" = gain |
| Driver exits later | positive | "you released brakes 10 m later" = loss |
| Same point | ~0 | No distance advantage |

This convention is **opposite** to `entry_distance_delta_m` (where positive = driver lifted later = gain). This is because:
- Entry: later lift = further from apex = more speed carried = gain → positive delta is good.
- Exit: earlier release = further from apex = sooner on power = gain → negative delta is good.

The LLM prompt must interpret the sign correctly per phase.

## Algorithm changes

### 1. Resample reference throttle and brake

(Same as entry gain algorithm — shared dependency.)

```python
ref_throttle = _try_column(ref_table, "throttle_norm")
ref_brake = _try_column(ref_table, "brake_norm")

ref_throttle_grid = resample_column(ref_dist, ref_throttle, track_length) if ref_throttle else None
ref_brake_grid = resample_column(ref_dist, ref_brake, track_length) if ref_brake else None
```

### 2. Detect reference exit points

```python
ref_exit_points = find_exit_points(
    ref_brake_grid, ref_throttle_grid,
    corner, thresholds,
)
```

### 3. Match driver and reference exit points

For each driver exit phase (`exit_brake`, `exit_throttle`, or merged `exit`), find the matching reference exit phase and compute the distance delta:

```python
# Build lookup for reference exits
ref_exit_by_phase = {phase: dist for phase, dist in ref_exit_points}

for phase_name, exit_idx in driver_exit_points:
    # Find matching reference phase distance
    ref_exit_idx = ref_exit_by_phase.get(phase_name)
    # Fallback: if driver has merged "exit" but ref has split phases,
    # use the closest reference phase
    if ref_exit_idx is None and phase_name == "exit":
        # Use whichever reference exit is closest to driver's exit
        ref_dists = [d for _, d in ref_exit_points]
        ref_exit_idx = min(ref_dists, key=lambda d: abs(d - exit_idx))
    
    exit_delta = ...  # speed delta at driver's exit distance
    if abs(exit_delta) > 1.0:
        corner_losses.append(CornerLoss(
            ...,
            phase_distance_m=float(exit_idx),
            reference_phase_distance_m=float(ref_exit_idx) if ref_exit_idx is not None else None,
            exit_distance_delta_m=float(ref_exit_idx - exit_idx) if ref_exit_idx is not None else None,
        ))
```

### 4. Include new fields in `to_dict()`

```python
if c.reference_phase_distance_m is not None:
    d["reference_phase_distance_m"] = round(c.reference_phase_distance_m, 1)
if c.exit_distance_delta_m is not None:
    d["exit_distance_delta_m"] = round(c.exit_distance_delta_m, 1)
```

## What the LLM prompt should do with exit gains

For exit gains (`loss_s < 0`, `phase` is `exit` / `exit_brake` / `exit_throttle`):

- If `exit_distance_delta_m < -3`: "You got back on power {abs(delta):.0f} m earlier in {corner_name}, carrying {speed_delta:.0f} kph more exit speed."
- If `exit_distance_delta_m ≈ 0` (within 3 m): "You carried {speed_delta:.0f} kph more exit speed in {corner_name}."
- If `exit_distance_delta_m > 0` (rare: driver exited later but still faster): "You carried {speed_delta:.0f} kph more at {corner_name} exit despite getting on power later."

For `exit_brake` specifically: "You released brakes {abs(delta):.0f} m earlier in {corner_name}."
For `exit_throttle` specifically: "You reached full throttle {abs(delta):.0f} m earlier in {corner_name}."

## Fallback behavior

If reference brake/throttle are not available, `find_exit_points()` falls back to zone boundary (`s_end_m`). The `exit_distance_delta_m` would be `s_end_m - driver_exit_m`, which is still meaningful ("you got to full throttle X m before the zone end"), but less precise than a reference-phase comparison. If both driver and reference fall back to zone boundary, `exit_distance_delta_m = 0` and the gain is purely speed-based.

## Acceptance criteria

- Reference throttle and brake are resampled onto the 1 m grid.
- `find_exit_points()` is called on reference traces, producing reference exit distances.
- `CornerLoss` gains `exit_distance_delta_m` and `reference_phase_distance_m` fields (shared with entry).
- Exit distance delta uses the sign convention `ref_exit_m - driver_exit_m` (negative = driver exits earlier = gain).
- Match logic handles the case where driver has merged `exit` but reference has split phases (and vice versa).
- Existing exit loss behavior is unchanged.
- `to_dict()` includes new fields when present.
- Tests cover reference exit detection, distance-delta calculation, and phase-matching edge cases.