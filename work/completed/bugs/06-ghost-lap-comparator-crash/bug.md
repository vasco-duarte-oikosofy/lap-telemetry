# Bug 06: 1-frame session-end laps crash compare_laps() with ValueError

## Observed

```
lap completed: lap 9, frames=1, lap_time=-0.10s
ValueError: max() arg is an empty sequence
  in lap_comparator.py:134
```

## Root cause

At session end, the `LapDetector` emits a `LapCompleted` event for the partial in-progress lap (1 frame, negative `lap_time_s`). `compare_laps()` tries to find valid lap times but finds none.

## Fix plan

Add a guard at the top of `LiveFactGenerator.generate()`:

```python
if event.frame_count < 50 or event.lap_time_s <= 0:
    log.debug("Skipping ghost lap (frames=%d, lap_time=%.2fs)", event.frame_count, event.lap_time_s)
    return
```

This prevents the Parquet conversion and `compare_laps()` call entirely for ghost laps.

## Files

- `product/python/lap_telemetry/coach/live_fact_generator.py`

## Test

`dev/scripts/test_ghost_lap_filter.py`

## Status

✅ Fixed in commit `50528e5`

- Ghost lap guard added at top of `LiveFactGenerator.generate()`:
  `if event.frame_count < 50 or event.lap_time_s <= 0: skip`
- 1-frame session-end laps no longer reach `compare_laps()`.

Moved to `work/completed/bugs/`.
