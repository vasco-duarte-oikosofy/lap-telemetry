# Bug 16: Slow/pitstop laps pass the partial-lap guard and produce bogus coaching

## Observed symptom

From `sessions/recorder_with_coach.txt` (session `20260529T143959Z`):

```
lap-telemetry: [coach] lap completed: lap 13, frames=4217, lap_time=84.42s
lap_telemetry.coach.live_fact_generator: Skipping coaching for partial lap 13 (...): no frames for requested lap
```

Lap 13 was silently skipped due to the unrelated bug-14 wrong-shard issue.
Had the Parquet path worked correctly (or the event.frames fallback fired),
the driver would have heard:

> "You lost twelve seconds at the apex of turn 4."

That utterance is physically impossible on a 71-second lap. The coaching
pipeline would have produced and spoken it.

## Root cause

`compare_laps()` in `lap_comparator.py` raises `PartialLapError` for two
coverage cases (added in bug 12):

- **tail-partial**: `min(dist) > lap_length × 0.10` — lap starts mid-track
- **head-partial**: `max(dist) < lap_length × 0.80` — lap ends mid-track

Lap 13 passes both checks:
- `min(dist) ≈ 0 m` ✓
- `max(dist) ≈ 3510 m` ✓ (full lap)

But `max(lap_time_s) = 84.42 s` vs reference `max(lap_time_s) = 71.242 s`
— **18.5% longer than reference**. Lap 13 is a pitstop or safety-car lap.
The car drove the full track distance but at drastically reduced speed
through at least one sector. The Δt trace accumulates a 13-second deficit
before turn 4. The `loss_s` at turn 4 reflects the time the car lost while
pitting, not a real driving error.

## Why 12.5 s phantom loss appears

The pitstop entry is near the turn 4 region. The car decelerates sharply
through that sector. `delta_t[apex_of_turn_4] ≈ +12 s` (car is 12 seconds
behind reference by that point). From apex to straight-end the car is still
~12 s behind. `loss_s = delta_t[straight_end] − delta_t[apex] ≈ 0 s`.
But the `loss_s` reported is **+12.486 s** at turn 4 minimum speed.

The turn 4 minimum speed in the pitstop lap is **107.9 kph** (pitlane speed
limiter keeping speed artificially high relative to a braked corner). The
reference minimum at turn 4 is **105.0 kph**. Because the driver appears
*faster* at that bin, `speed_delta < 0` and the `minimum_speed` phase
detects a "gain" — but `loss_s = delta_t[straight_end] − delta_t[apex_idx]`
returns **+12.5 s** because by that point in the lap the Δt is already
deeply negative (the car has been in the pit). The `abs(speed_delta) > 0.5`
threshold is met, so the entry into the loss/gain list is not filtered.
The item lands in `top_losses` because the sign of `loss_s` is positive.

## Guard condition needed

After the existing distance-coverage guard in `compare_laps()`, add a
duration guard:

```python
# Bug 16: reject pitstop / safety-car laps whose duration is implausibly
# long relative to the reference. A threshold of 1.20 catches pitstop laps
# (typically +15–30% over reference) while allowing outlaps, in-laps, and
# legitimately slow laps that stay within 20% of reference pace.
_driver_max_time = max((t for t in current_table.column("lap_time_s").to_pylist()
                        if t is not None and t > 0), default=0.0)
_ref_max_time    = max((t for t in ref_table.column("lap_time_s").to_pylist()
                        if t is not None and t > 0), default=0.0)
_SLOW_LAP_THRESHOLD = 1.20

if _ref_max_time > 0 and _driver_max_time > _ref_max_time * _SLOW_LAP_THRESHOLD:
    raise PartialLapError(
        f"lap duration {_driver_max_time:.1f}s is "
        f"{_driver_max_time / _ref_max_time * 100:.0f}% of reference "
        f"{_ref_max_time:.1f}s — likely pitstop or safety-car lap"
    )
```

The duration check must run **after** the reference table is loaded
(so `_ref_max_time` is available) and **before** the JS pipeline call.

## Evidence from session

Session: `session_20260529T143959Z_bahrain-outer-circuit_lmu.parquet`
Reference: `bahrain-outer-circuit_dkr-engineering-4-elms25_time_01.11.380.parquet`
Track model: `bahrain-outer-circuit_dkr-engineering-4-elms25.json`

```
lap 13: frames=4217, max(lap_time_s)=84.42s
        reference max(lap_time_s)=71.242s
        ratio = 118.5%  (> 20% over reference)

compare_laps() result without guard:
  LOSS turn 4  minimum_speed  loss=+12.486s  driver=107.9 kph vs ref=105.0 kph
  LOSS turn 4  exit           loss=+12.481s
  LOSS turn 1  minimum_speed  loss=+0.815s
  delta=+13.178s
```

## Files to fix

### `lap_comparator.py`

Add the duration guard described above. The threshold (`1.20`) should be
a module-level constant `_SLOW_LAP_RATIO_THRESHOLD` so it is easy to tune.

## Tests to add

### `test_pitstop_lap_raises_partial_lap_error`

Using the session file and reference:
```python
compare_laps(SESSION, REF, model, lap_number=13)
# must raise PartialLapError matching "pitstop" or "duration"
```

### `test_normal_slow_lap_still_coaches`

Build a synthetic lap that is 15% slower than reference (within threshold).
Assert `compare_laps` does NOT raise `PartialLapError`.

### `test_threshold_boundary`

Build a lap at exactly `ref_time × 1.20` — assert no error.
Build a lap at `ref_time × 1.21` — assert `PartialLapError`.
