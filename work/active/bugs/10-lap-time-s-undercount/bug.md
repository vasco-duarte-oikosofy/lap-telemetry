# Bug 10: `lap_time_s` column underestimates lap time by 0–180 ms

## Observed

`extract_reference_lap.py` uses `max(lap_time_s)` per segment to compute lap duration.
For a lap the driver confirmed as **1:11.3xx** on-screen, the script reports **1:11.079**
(lap 23) or **1:11.242** (lap 24) — both short of the real time.

Session: `sessions/session_20260528T174221Z_bahrain-outer-circuit_lmu.parquet`

| Lap | `max(lap_time_s)` | offset-corrected | frames/50 Hz | driver HUD |
|-----|-------------------|------------------|--------------|------------|
| 23  | 1:11.079          | 1:11.238         | 1:11.140     |            |
| 24  | 1:11.242          | 1:11.380         | 1:11.340     | ~1:11.3xx  |

## Root cause

When `lap_number` increments, `lap_time_s` resets immediately to a **negative** value
(typically −0.000 to −0.180 s) rather than to 0. This negative value represents how
far past the scoring-module update the finish-line crossing already was when the SHM
was next polled. The last frame recorded under the old `lap_number` therefore reflects
a time *before* the true crossing, not at it.

```
last frame of lap N :  lap_time_s = 71.079   (short of crossing)
first frame of lap N+1: lap_time_s = -0.158  (already -0.158 s into new lap)
true finish time   :  71.079 + 0.158 = 71.237 s
```

The systematic shortfall equals `abs(first lap_time_s of lap N+1)` when that value is
negative. When it is 0 or positive (rare), `max(lap_time_s)` is accurate.

## Fix plan

In `extract_reference_lap.py` (and any other place that computes lap duration from
`lap_time_s`), replace:

```python
duration = max(lap_time_s[start:end])
```

with:

```python
max_t      = max(lap_time_s[start:end])
first_next = lap_time_s[end] if end < len(lap_time_s) else 0.0
offset     = abs(first_next) if first_next < 0 else 0.0
duration   = max_t + offset
```

This requires one look-ahead row (the first row of the next segment), which is always
available for non-final segments.

For the final segment (last lap before session end) the offset cannot be recovered —
fall back to `max(lap_time_s)` as today.

## Reproducer

See `reproducer.py` in this folder. Run from project root:

```powershell
python work/active/bugs/10-lap-time-s-undercount/reproducer.py
```

Prints the boundary analysis for every lap in the Bahrain Outer session, showing
`max(lap_time_s)`, the offset, and the corrected time.

## Affected files

- `dev/scripts/extract_reference_lap.py` — `main()` duration computation
- `dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md` — procedure docs

## Status

🐛 Open
