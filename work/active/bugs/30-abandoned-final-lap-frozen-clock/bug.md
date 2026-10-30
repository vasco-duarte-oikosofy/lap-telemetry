# Bug 30 — Abandoned final lap with a frozen game clock passes every complete-lap guard

## Symptom

The last lap of a session that ran out of time mid-lap is reported as a
**complete** lap with a duration that is simply `max(lap_time_s)` of a frozen
telemetry clock. It is *not* rejected by any of the bug-22 guards, so
`export_fastest_reference_laps.py` / `update_reference_and_coaching_model.py`
would happily make it the reference lap.

Observed on São Paulo / Interlagos (P3), session
`session_20260628T062002Z_autodromo-jose-carlos-pace_lmu_practice.parquet`,
final segment (`lap_number=6`):

| quantity | value |
|---|---|
| lap chosen by `find_complete_laps()` | `lap 6 @ 89.679 s` |
| rows in segment | 5 845 (a normal lap here is ~4 500) |
| distinct `session_time_s` values | 450 → **5 395 duplicated rows** (~13 rows per 0.2 s tick) |
| `session_time_s` wall-clock span | 89.8 s — agrees with the bogus time because both come from the same frozen clock |
| `lap_distance_m` first / last / peak | 4272.19 / 4106.24 / 4272.19 (peak is the *previous* lap's end) |
| distance actually covered | 4 103 m of 4 281 m → **166 m short of the line** |
| `session_time_remaining_s` at segment end | `0.0` (session expired; clock frozen at 1080.0) |
| `scoring_last_lap_time_s` at segment end | 92.041 (that is *lap 5*'s time — the scorer lags one lap here) |

89.679 s would have beaten the real reference (90.354 s) by 0.675 s on a lap
that never crossed the line.

## Root cause

Every guard in `find_complete_laps()` is fooled by the same clock freeze:

1. `segment_wall_clock_span()` vs `authoritative_duration()` — both read
   `session_time_s` / `lap_time_s` from the frozen clock, so the "wall clock
   agrees with the claimed duration" check passes by construction.
2. `segment_covers_full_lap()` — checks `last >= peak - 200`. The peak
   (4272.19) is inherited from the first frame of the segment (the previous
   lap's end distance, a documented quirk), and the trace stops at 4106.24,
   which is only 166 m below the peak — inside the 200 m tolerance. It never
   wrapped to the line on its own.
3. The row-count outlier filter drops segments **below** 95 % of the median
   row count; this segment has 30 % *more* rows, so it survives.
4. `authoritative_duration()` has no next segment to take a lap-start ET
   difference from, so it falls back to `max(lap_time_s)` (bug 13's fallback),
   which here is a frozen-clock value, not a real lap time.

## Reproduction

Read-only, no writes:

```bash
export PYTHONPATH=product/python
python3 - <<'PY'
import sys
sys.path.insert(0, "dev/scripts"); sys.path.insert(0, "product/python")
import pyarrow.parquet as pq
from export_fastest_reference_laps import (
    find_complete_laps, segment_wall_clock_span)

t = pq.read_table("sessions/session_20260628T062002Z_"
                  "autodromo-jose-carlos-pace_lmu_practice.parquet")
lap = min(find_complete_laps(t), key=lambda c: c[1])
print("chosen:", lap[0], round(lap[1], 3))
s, e = lap[2], lap[3]
cols = lambda n: t.column(n).to_pylist()[s:e]
print("rows", e - s, "distinct session_time", len(set(cols("session_time_s"))))
print("span", round(segment_wall_clock_span(t, s, e), 3))
print("distance last", cols("lap_distance_m")[-1],
      "remaining", cols("session_time_remaining_s")[-1])
PY
```

Current output: `chosen: 6 89.679 … distance last 4106.24 remaining 0.0`.
Expected: this segment is rejected; São Paulo's fastest legitimate lap is
practice lap 9 of `session_20261030T151318Z` at 90.354 s.

## Impact

Any bulk scan of this track's sessions (`sessions/session_*jose-carlos*.parquet`)
picks 89.679 s and would name a reference lap `_time_01.29.679.parquet`, deleting
the honest 90.354 s reference (the export audit only checks *how many* files
changed, not whether the lap is real). `c723ddc` deliberately passed only the
practice session that holds the 90.354 s lap to avoid this.

## Fix direction (not implemented)

Reject a candidate segment when the recorder clock stopped advancing:

- `session_time_remaining_s` reaching `0.0` inside the segment, **or**
- duplicated `session_time_s` values (the segment is not a contiguous 50 Hz
  trace), **or**
- `segment_covers_full_lap()` requiring the trace's *own* wrap (`last` close to
  the lap length) instead of `peak - 200` where the peak can be inherited from
  the previous lap.

The duplicate-timestamp check is the cheapest and catches the whole class
(recorder catch-up / frozen-frame writes), not just this session. Add a
regression fixture next to `test_bug16_slow_lap_guard.js` (synthetic segment:
frozen `session_time_s`, duplicated rows, session_time_remaining → 0) and
assert `find_complete_laps()` returns nothing for it.

## Files

- `dev/scripts/export_fastest_reference_laps.py` — `find_complete_laps()`,
  `segment_covers_full_lap()`, `segment_wall_clock_span()`
- `product/python/lap_telemetry/parquet_utils.py` — `authoritative_duration()`
  (the `max(lap_time_s)` fallback is what surfaces the frozen value)
- Related: bug 13 (`max(lap_time_s)` undercount), bug 16 (implausible lap
  durations), bug 22 (restart-truncated segments)
