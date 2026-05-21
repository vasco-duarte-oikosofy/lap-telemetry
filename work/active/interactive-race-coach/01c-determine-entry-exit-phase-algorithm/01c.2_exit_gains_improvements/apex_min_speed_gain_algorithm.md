# Apex minimum-speed gain algorithm

## Status

Easiest of the three gain improvements. Detection already works. Two changes needed: (1) surface the apex offset, (2) compute real integrated time for **gains only** — losses keep `speed_delta / 100.0` unchanged.

## Scope

**This algorithm only changes how gains are measured for minimum_speed phases.** Losses continue to use `loss_s = speed_delta / 100.0` as before. The delta-time computation and `apex_offset_m` field are added without touching any loss logic.

## Core insight

A minimum-speed gain doesn't just happen at the apex — it compounds down the entire straight. If the driver carries 5 kph more through the apex, that advantage accumulates until the driver lifts off for the next corner. The real **time gain** is the change in cumulative time difference between driver and reference from the apex to the end of the straight.

```
gain_s = delta_t[straight_end] - delta_t[apex]
```

- `delta_t > 0` → driver is behind (took more time to reach this point)
- `delta_t < 0` → driver is ahead (took less time)
- `gain_s < 0` → driver gained time on this segment (further ahead at end of straight than at apex)

Example: driver is −0.15s ahead at the apex (faster), and −0.25s ahead at the next braking zone. Time gained on the straight = (−0.25) − (−0.15) = −0.10s. The driver gained 0.10s from apex to end of straight.

## Delta-time trace

### Computation

Build a 1 m resolution delta-time trace from the resampled speed grids:

```python
def compute_delta_time_trace(
    driver_speed: list[float],  # kph, 1 m grid
    ref_speed: list[float],     # kph, 1 m grid
    track_length: int,
) -> list[float]:
    """Compute cumulative time delta at each meter.

    delta_t[s] = driver_cumtime[s] - ref_cumtime[s]
    Positive = driver behind (slower cumulative time to this point).
    Negative = driver ahead (faster cumulative time to this point).
    """
    driver_cumtime = [0.0] * track_length
    ref_cumtime = [0.0] * track_length
    dt_driver = 0.0
    dt_ref = 0.0

    for s in range(track_length):
        # Time to traverse 1 m at this speed. 1 m / (speed_kph / 3.6) = 3.6 / speed_kph
        driver_speed_ms = max(driver_speed[s], 1.0) / 3.6  # clamp to avoid division by zero
        ref_speed_ms = max(ref_speed[s], 1.0) / 3.6
        dt_driver += 1.0 / driver_speed_ms
        dt_ref += 1.0 / ref_speed_ms
        driver_cumtime[s] = dt_driver
        ref_cumtime[s] = dt_ref

    return [driver_cumtime[s] - ref_cumtime[s] for s in range(track_length)]
```

### Notes

- **MUST use the same delta-T calculation as the web UI.** The existing web JS (`product/web/js/pipeline.js`, `computeDeltaT()`) computes delta-t from the `lap_time_s` column directly: `dt[i] = (sessionLapTime[i] - refLapTime[i]) * 1000`. This is the ground truth — it uses the actual recorded elapsed time at each distance. Our current Python implementation reconstructs cumulative time from speed (`time_per_meter = 1 / (speed_kph / 3.6)`, summed over distance), which is an approximation. We MUST replace `compute_delta_time_trace()` with a version that resamples `lap_time_s` onto the same 1 m grid and then computes `delta_t[i] = driver_lap_time[i] - ref_lap_time[i]`, matching the web JS approach exactly. See `product/web/js/pipeline.js` line 180.
- Speeds clamped to 1.0 kph minimum (0.28 m/s) to avoid division by zero for pit lane / stopped car.
- The trace covers the entire lap, so it can be queried at any distance.
- `delta_t[len-1]` ≈ `lap_time_delta_s` (the total lap time difference). Small discrepancy from start/finish alignment is expected.

## End of the straight

The end of the straight (where compounding stops) is the **next point where the driver lifts off throttle or applies brakes** — exactly matching the existing entry detection thresholds:

| Signal | Threshold | Meaning |
|--------|-----------|---------|
| Throttle lift | < 0.9 (90%) | Driver started lifting off throttle |
| Brake application | > 0.05 (5%) | Driver started braking |

This is already what `find_entry_point()` detects. The end of the straight after corner N is the entry point of corner N+1.

### Finding the next corner's entry

```python
def find_straight_end_after_corner(
    corner_index: int,
    corners: list[Corner],
    driver_speed: list[float],
    driver_throttle: list[float] | None,
    driver_brake: list[float] | None,
    thresholds: PhaseDetectionThresholds,
    track_length: int,
) -> int:
    """Find the distance where the straight after corner_index ends.

    This is the entry point of the next corner (throttle lift or brake onset).
    For the last corner, returns track_length - 1 (end of lap).
    """
    if corner_index >= len(corners) - 1:
        # Last corner: measure to end of lap
        return track_length - 1

    next_corner = corners[corner_index + 1]
    entry_idx, _method = find_entry_point(
        driver_speed, driver_throttle, driver_brake,
        next_corner, thresholds,
    )
    return entry_idx
```

### Edge case: last corner

After the last turn on the track, there is no next braking zone. The speed advantage compounds all the way to the start/finish line. In this case:

```python
end_of_straight = track_length - 1  # end of lap
```

This gives the total time gained from the last apex to the line, which is the correct accounting for that lap.

### Example: Barcelona turn 10 (last turn before start/finish)

- Driver apexes turn 10 at 95 kph, reference at 90 kph (5 kph advantage).
- `delta_t[apex_10] = -0.15` (driver 0.15s ahead at apex).
- `delta_t[end_of_lap] = -0.25` (driver finishes 0.25s ahead at the line).
- `gain_s = delta_t[end] - delta_t[apex] = (-0.25) - (-0.15) = -0.10` → driver gained 0.10s from the last apex to the line.
- In `CornerLoss`, `loss_s = -0.10` (negative = gain, same sign convention as before).

## Algorithm changes

### 1. Compute the delta-time trace

In `compare_laps()`, after resampling speed grids onto the 1 m grid, compute:

```python
delta_t = compute_delta_time_trace(driver_speed, ref_speed_grid, track_length)
```

This is computed once for the entire lap and reused for all corners.

### 2. Find the end of the straight for each corner

```python
straight_end = find_straight_end_after_corner(
    corner_idx, track_model.corners,
    driver_speed, driver_throttle_grid, driver_brake_grid,
    thresholds, track_length,
)
```

Uses the driver's throttle/brake traces (not the reference's — the end of the straight is where **this** driver lifts off for the next corner).

### 3. Compute minimum_speed — losses unchanged, gains use delta-time

**Losses stay exactly as they are:** `loss_s = speed_delta / 100.0` where `speed_delta = ref_min - driver_min`. No change.

**Gains get real integrated time:**

```python
driver_min, ref_min, speed_delta, driver_apex_m, ref_apex_m = (
    compute_minimum_speed_per_corner(driver_speed, ref_speed_grid, corner)
)

if abs(speed_delta) > 0.5:
    if speed_delta > 0:
        # LOSS — unchanged heuristic
        loss_s = speed_delta / 100.0
    else:
        # GAIN — real integrated time from apex to end of straight
        # delta_t[s] = driver_cumtime - ref_cumtime. Negative = driver ahead.
        # gain_s negative means driver gained time (further ahead at end of straight).
        apex_delta_t = delta_t[int(driver_apex_m)]
        straight_end_delta_t = delta_t[straight_end]
        loss_s = straight_end_delta_t - apex_delta_t  # negative = gain

    corner_losses.append(CornerLoss(
        corner_id=corner.id,
        corner_name=corner.name,
        apex_distance_m=corner.apex_s_m,
        phase="minimum_speed",
        loss_s=loss_s,
        driver_value=driver_min,
        reference_value=ref_min,
        unit="km/h",
        confidence="high" if abs(speed_delta) > 2.0 else "medium",
        phase_distance_m=driver_apex_m,
        driver_apex_distance_m=driver_apex_m,
        reference_apex_distance_m=ref_apex_m,
        apex_offset_m=ref_apex_m - driver_apex_m,
    ))
```

### 4. Add `apex_offset_m` field to `CornerLoss`

```python
@dataclass
class CornerLoss:
    # ... existing fields ...
    apex_offset_m: float | None = None  # ref_apex - driver_apex; positive = driver apexed earlier
```

Populate for `minimum_speed` phases only:
```python
apex_offset_m = ref_apex_m - driver_apex_m
```

### 5. Include in `to_dict()`

```python
if c.apex_offset_m is not None:
    d["apex_offset_m"] = round(c.apex_offset_m, 1)
```

## What the LLM prompt should do with gains

For `minimum_speed` gains (`loss_s < 0`, real integrated time):

- If `abs(apex_offset_m) > 5` and apex_offset_m > 0: "You gained {abs(loss_s):.2f}s through {corner_name}, apexing {apex_offset_m:.0f} m earlier."
- If `abs(apex_offset_m) ≤ 5`: "You gained {abs(loss_s):.2f}s through {corner_name}."
- If `apex_offset_m < 0`: "You gained {abs(loss_s):.2f}s through {corner_name} despite apexing {abs(apex_offset_m):.0f} m later."
- Speed delta is still reported via `driver_value` / `reference_value`: "You carried {speed_delta:.0f} kph more minimum speed."

The LLM can now say both the speed advantage *and* the time it was worth.

## `loss_s` semantics

For **minimum_speed only**:

| | `loss_s` value | Meaning |
|--|--|--|
| **Loss** | `speed_delta / 100.0` (heuristic) | Unchanged from current behavior |
| **Gain** | `delta_t[straight_end] - delta_t[apex]` (real time) | Integrated time gained from apex to end of straight |

The sign convention is the same as before: `loss_s > 0` means the driver lost time, `loss_s < 0` means the driver gained time. But the *units* differ between losses (heuristic seconds) and gains (real seconds). This is intentional — losses keep their existing behavior, and gains get accurate time measurement.

### TODO: Extend delta-time to entry and exit gains

Entry and exit gains should also use delta-time. The pattern is the same:

```
gain_s = delta_t[straight_end] - delta_t[phase_point]
```

This is deferred to the entry and exit gain implementation slices.

## Acceptance criteria

- `compute_delta_time_trace()` produces a trace whose final value ≈ `lap_time_delta_s`.
- `find_straight_end_after_corner()` returns next corner's entry point (using throttle lift / brake onset thresholds), or `track_length - 1` for the last corner.
- `CornerLoss` has `apex_offset_m`, populated for `minimum_speed` phases.
- For minimum_speed **losses**: `loss_s = speed_delta / 100.0` — completely unchanged.
- For minimum_speed **gains**: `loss_s = delta_t[straight_end] - delta_t[apex]` — real integrated time, negative for gains.
- `to_dict()` includes `apex_offset_m` when present.
- The `compute_minimum_speed_per_corner()` function signature and return type are unchanged.
- Tests cover: delta-time trace correctness, straight-end detection, last-corner edge case, gain with apex offset, loss behavior unchanged.