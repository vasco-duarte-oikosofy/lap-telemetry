# Entry gain algorithm

## Current behavior

`find_entry_point()` uses **only the driver's** throttle/brake/speed traces:

1. Walk forward from `(s_start_m - look_back_m)` toward `apex_s_m`.
2. Find the first throttle drop below 0.9 after sustained ≥ 0.9 → `driver_entry_m`.
3. Compare: `driver_speed[driver_entry_m]` vs `ref_speed[driver_entry_m]`.
4. If `entry_delta = ref_speed - driver_speed > 1.0` → loss; `< -1.0` → gain.

For a **loss**, this is coaching-meaningful: "at the point where you lifted, you were 4 kph slower than reference."

For a **gain**, it's incomplete: it tells us the driver was faster at their own lift point, but not *how* they were faster. The most actionable entry-gain fact is a **distance delta**: "you lifted 8 m later than reference" — meaning the driver carried speed deeper into the braking zone.

## What's needed

### Detect the reference's entry point

Run the same `find_entry_point()` algorithm on the **reference lap's** resampled throttle/brake/speed traces. This produces `reference_entry_m` — the distance where the reference driver lifted off throttle (or hit speed peak).

### New fields on `CornerLoss` for entry gains

```python
@dataclass
class CornerLoss:
    # ... existing fields ...
    entry_distance_delta_m: float | None = None  # reference_entry - driver_entry; positive = driver lifted later
    reference_phase_distance_m: float | None = None  # distance where reference's phase was detected
```

For entry phases:
- `entry_distance_delta_m = reference_entry_m - driver_entry_m`
  - Positive → driver lifted later (further from apex), i.e. driver braked later = carried more speed = gain.
  - Negative → driver lifted earlier (closer to apex), i.e. driver braked earlier = potential loss or hesitation.
- `reference_phase_distance_m = reference_entry_m` — so the LLM can say "reference lifted at 420 m."

### Speed comparison for entry gains

For gains, report the speed comparison at the **reference's** entry distance, not just the driver's:

- `driver_value` = `driver_speed[driver_entry_m]` (speed at driver's lift point)
- `reference_value` = `ref_speed[driver_entry_m]` (reference's speed at driver's lift point — current behavior)
- `loss_s = (reference_value - driver_value) / 100.0` (negative for gains)
- The `phase_distance_m` remains `driver_entry_m` (the driver's entry distance)

The reference's entry distance is available via `reference_phase_distance_m` for distance-delta coaching, but the primary speed comparison stays at the driver's entry distance for consistency with losses.

### Why not compare at reference distance instead?

For losses, we compare at the driver's entry distance because the driver's action is what's being corrected. For gains, comparing at the driver's lift point is also fine — the driver was simply faster there. But the **additional** insight ("you lifted 8 m later") is only available if we also detect the reference's entry.

We choose to keep `driver_value` and `reference_value` comparing at `phase_distance_m` (= driver's entry), and add `entry_distance_delta_m` as the new actionable fact. This avoids changing the interpretation of existing fields.

## Algorithm changes

### 1. Resample reference throttle and brake

In `compare_laps()`, after resampling `ref_speed`, also resample:

```python
ref_throttle = _try_column(ref_table, "throttle_norm")
ref_brake = _try_column(ref_table, "brake_norm")

ref_throttle_grid = resample_column(ref_dist, ref_throttle, track_length) if ref_throttle else None
ref_brake_grid = resample_column(ref_dist, ref_brake, track_length) if ref_brake else None
```

These grids are currently not computed. The driver's pedal traces are resampled but the reference's are not.

### 2. Detect reference entry point

```python
ref_entry_idx, ref_entry_method = find_entry_point(
    ref_speed_grid, ref_throttle_grid, ref_brake_grid,
    corner, thresholds,
)
```

### 3. Populate new fields on entry CornerLoss

```python
entry_delta = ref_entry_speed - driver_entry_speed
if abs(entry_delta) > 1.0:
    corner_losses.append(CornerLoss(
        ...,
        phase_distance_m=float(entry_idx),
        reference_phase_distance_m=float(ref_entry_idx),
        entry_distance_delta_m=float(ref_entry_idx - entry_idx),
    ))
```

### 4. Include new fields in `to_dict()`

```python
if c.reference_phase_distance_m is not None:
    d["reference_phase_distance_m"] = round(c.reference_phase_distance_m, 1)
if c.entry_distance_delta_m is not None:
    d["entry_distance_delta_m"] = round(c.entry_distance_delta_m, 1)
```

## What the LLM prompt should do with entry gains

For entry gains (`loss_s < 0` and `phase == "entry"`):
- If `entry_distance_delta_m > 0`: "You lifted {entry_distance_delta_m:.0f} m later than reference into {corner_name}, carrying {speed_delta:.0f} kph more speed."
- If `entry_distance_delta_m ≤ 0` (rare: driver lifted earlier but still faster): "You carried {speed_delta:.0f} kph more into {corner_name} despite lifting earlier."

## Fallback behavior

If reference throttle/brake are not available, `ref_entry_idx` falls back to `speed_peak` or `zone_start` detection on `ref_speed_grid`. The `entry_distance_delta_m` is still computed but may be less precise. If the reference also has no speed peak in the search range, `reference_phase_distance_m` and `entry_distance_delta_m` are set to `None`.

## Acceptance criteria

- Reference throttle and brake are resampled onto the 1 m grid.
- `find_entry_point()` is called on reference traces, producing `reference_entry_m`.
- `CornerLoss` gains `entry_distance_delta_m` and `reference_phase_distance_m` fields.
- `to_dict()` includes new fields when present.
- For entry losses (`loss_s > 0`), behavior is unchanged (new fields are populated but not required for coaching).
- For entry gains (`loss_s < 0`), `entry_distance_delta_m` tells the LLM how much later/earlier the driver lifted.
- Existing tests pass; new tests cover reference entry detection and distance-delta calculation.