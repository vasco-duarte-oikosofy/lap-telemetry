# Slice 10c: Use `scoring_last_lap_time_s` as authoritative lap duration

## Context

10b shipped four new `scoring_*` columns and we recorded a live session
(`session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet`). The evaluation
confirms the fix strategy and quantifies the undercount.

## What 10b told us

`scoring_last_lap_time_s` = `scor_v.mLastLapTime` — the sim's own authoritative
duration for the **most recently completed lap**. It lives at scoring cadence (~5 Hz,
33% of rows populated) and holds the **previous** lap's time, so it appears in the
**next segment's rows**, not the current one.

Measured undercount on Bahrain Outer, confirmed from live session:

| Lap | `max(lap_time_s)` | `scoring_last_lap_time_s`* | undercount |
|-----|-------------------|---------------------------|------------|
| 3   | 71.562 s          | 71.679 s  (read in lap 4) | **117 ms** |
| 5   | 71.952 s          | 72.029 s  (read in lap 6) | **77 ms**  |
| 6   | 71.724 s          | 71.900 s  (read in lap 7) | **176 ms** |

*Read as `max(scoring_last_lap_time_s)` in the immediately following segment.

Lap 4 (78.88 s — slow lap, probably invalid) did **not** update `mLastLapTime`; the
field stayed at the previous lap's value (71.679 s) through laps 4 and 5. This is
the sim's own validity gate: if the lap didn't count, `mLastLapTime` doesn't update.

`scoring_time_into_lap_s` is unreliable as a lap-end timestamp — the stale boundary
value from the previous lap dominates `max()` and makes it look wrong.

## Algorithm for authoritative duration

For segment `seg_idx` (covering rows `[start, end)`), the authoritative duration is:

```python
def _authoritative_duration(
    table: pa.Table,
    seg_idx: int,
    segments: list[tuple[int, int, int]],
) -> float:
    """Return authoritative lap duration for segments[seg_idx].

    Reads scoring_last_lap_time_s from the NEXT segment (where mLastLapTime
    holds this lap's official time). Falls back to max(lap_time_s) if:
      - the column is absent (pre-10b parquet)
      - no next segment exists (last lap)
      - the next segment's value is None or > 1 s away from max(lap_time_s)
        (lap didn't count, so mLastLapTime didn't update)
    """
    _, start, end = segments[seg_idx]
    fallback = max(table.column("lap_time_s").to_pylist()[start:end])

    # No next segment → this is the last (likely partial) lap; use fallback
    if seg_idx + 1 >= len(segments):
        return fallback

    # Column absent → pre-10b recording
    if "scoring_last_lap_time_s" not in table.schema.names:
        return fallback

    _, next_start, next_end = segments[seg_idx + 1]
    next_vals = [
        v for v in table.column("scoring_last_lap_time_s").to_pylist()[next_start:next_end]
        if v is not None
    ]
    if not next_vals:
        return fallback

    candidate = max(next_vals)

    # Sanity check: within 1 s of max(lap_time_s).
    # If the lap was invalid, mLastLapTime didn't update and the candidate
    # reflects a different (older) lap — discard it.
    if abs(candidate - fallback) > 1.0:
        return fallback

    return candidate
```

The `> 1.0 s` tolerance is deliberately wide — it only rejects clear mismatches
(like the lap 4 case where the candidate was 71.679 s for a 78.88 s lap).

## Scope

Fix `dev/scripts/extract_reference_lap.py` to use `_authoritative_duration()`.

Specifically, three places call `max(lap_t_col)` or `max(t.column('lap_time_s')...)`:

1. **Line 76** — the listing loop that prints all segments
2. **Lines 100–102** — the `--lap` flag picks the *fastest* segment by duration
3. **Line 119** — the final extracted duration used for display and auto-naming

Replace all three with `_authoritative_duration(t, seg_idx, segments)`.

The output filename is auto-named from `EXTRACT_AND_STORE_REFERENCE_LAP.md` using
the printed duration, so fixing line 119 is enough for the filename to be correct.
No other files are in scope for this slice.

## Non-goals

- Do **not** change `lap_comparator.py` (uses `max(lap_time_s)` for delta — a
  separate problem, candidates for 10d).
- Do **not** change `dist/compare.html` or session-summary displays.
- Do **not** backfill old parquets.
- Do **not** remove or rename `lap_time_s`.

## Backward compatibility

`_authoritative_duration()` returns `max(lap_time_s)` whenever:
- the `scoring_last_lap_time_s` column is absent (old parquets)
- the candidate is > 1 s away from `max(lap_time_s)` (lap not counted by sim)
- no next segment exists

Old parquet users see no change. New parquets get corrected durations silently.

## Tests

Add to `tests/` (pytest):

1. **test_authoritative_duration_from_next_segment** — build a synthetic two-lap
   table where `scoring_last_lap_time_s` in lap 2 rows = 71.679, `max(lap_time_s)`
   for lap 1 = 71.562. Assert `_authoritative_duration(t, 0, segs) == 71.679`.

2. **test_fallback_when_column_absent** — same table but without the
   `scoring_last_lap_time_s` column. Assert result == 71.562.

3. **test_fallback_when_lap_invalid** — `scoring_last_lap_time_s` in next segment
   = 71.679 but `max(lap_time_s)` for current lap = 78.883 (> 1 s difference).
   Assert result == 78.883 (fallback).

4. **test_fallback_for_last_segment** — no next segment exists.
   Assert result == fallback `max(lap_time_s)`.

5. **integration: extract from live session** — run `_authoritative_duration` on
   `sessions/session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet` for laps 3,
   5, 6. Assert results match `[71.679, 72.029, 71.900]` (within 0.001 s tolerance).

## Acceptance

- `python dev/scripts/extract_reference_lap.py sessions/session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet`
  shows corrected durations in the segment listing for laps where data is available.
- The lap 6 reference extracted from that session is named `*_time_01.11.900.parquet`
  (not `*_time_01.11.724.parquet` as before).
- `pytest tests/` passes.
- Old-parquet workflow is unchanged (test with any pre-10b session file).
