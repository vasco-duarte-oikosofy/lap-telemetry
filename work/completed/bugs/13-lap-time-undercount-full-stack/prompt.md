# Bug 13: `max(lap_time_s)` undercount propagates through the full stack

## Context

Bug 10c fixed `extract_reference_lap.py` to use `scoring_last_lap_time_s` from
the next segment as authoritative lap duration (commit `43771f7`). That fix was
scoped to the extraction script only. Every other consumer of lap duration still
reads `max(lap_time_s)`, which is consistently 77–176 ms short of the true
finish-line time (the sim resets `lap_time_s` to a negative offset before the
last frame's value can reflect the actual crossing moment).

## Affected sites

### 1. `product/python/lap_telemetry/coach/lap_comparator.py` — lines 180–182

```python
driver_lap_time = max(t for t in current_lap_times if t is not None and t > 0)
ref_lap_time    = max(t for t in ref_lap_times    if t is not None and t > 0)
lap_time_delta  = driver_lap_time - ref_lap_time
```

`lap_time_delta_s` is included in the `LapComparisonFacts` struct sent to the
LLM. Both sides are undercount; the error does not cancel because each lap has
a different boundary offset (77–176 ms per lap). Observed delta error: 0–100 ms
typical, up to 200 ms worst-case on consecutive laps with very different offsets.

**Driver lap fix**: when `lap_number` is supplied, the session parquet still
has the next segment in it, so `_authoritative_duration()` (same algorithm as
the extract script) can be applied — read `scoring_last_lap_time_s` from the
first rows of the immediately following segment.

**Reference lap fix**: the reference is an extracted single-segment parquet.
There is no next segment, so the fallback `max(lap_time_s)` must be accepted —
BUT `scoring_last_lap_time_s` is also populated within the reference segment
itself (because the recorder writes it on every row once it becomes available).
`max(scoring_last_lap_time_s)` *within* the reference segment is the right
authoritative duration for that lap (confirmed by 10b data).

### 2. `product/python/lap_telemetry/summary.py` — `_run_file()` ~line 168

```python
max_lap_t    = max(seg_lap_t) if seg_lap_t else 0.0
duration_str = _fmt_duration(max_lap_t)
```

The per-lap duration column in `lap-telemetry summary <file>` is always
77–176 ms shorter than the HUD time. This confuses the user when correlating
against the in-game timer.

**Fix**: apply `_authoritative_duration()` (same algorithm, can be shared
as a helper in a new `product/python/lap_telemetry/parquet_utils.py`).
For the last segment (no next segment) the fallback is fine — it's typically
a partial/in-progress lap.

### 3. `product/web/js/pipeline.js` — `annotateSegments()` ~line 108

```javascript
seg.duration = mt;   // mt = max(lap_time_s) in the segment
```

`seg.duration` drives two things:
- **Fastest-lap ★ labelling**: `bestDur` comparisons use `max(lap_time_s)`.
  Two laps within 100 ms of each other can get the ★ on the wrong lap if
  their boundary offsets differ by > their true delta.
- **Δt endpoint in the UI**: the comment at line 240 notes the smoothed Δt at
  the last bin equals `max(lap_time_s)` delta — this is the number shown in
  the "end" tooltip and the `Δ:` readout. It is the difference of two
  undercounts, so the error is the difference of their offsets.

`scoring_last_lap_time_s` is already in the parquet schema (added by bug 10b)
and is loaded by `readColumns`. The authoritative duration for any segment can
be computed in JS as:

```javascript
// In annotateSegments — AFTER building per-segment maxDist/minDist:
// For segment i, the authoritative duration is the max of
// scoring_last_lap_time_s in segment i+1 (same algorithm as Python).
// Fall back to seg.duration (max lap_time_s) if not available.
function _authDuration(segments, scoringLastLapTime, i) {
  const fallback = segments[i].duration;
  if (!scoringLastLapTime || i + 1 >= segments.length) return fallback;
  const next = segments[i + 1];
  let best = -Infinity;
  for (let k = next.start; k < next.end; k++) {
    const v = scoringLastLapTime[k];
    if (v != null && Number.isFinite(v) && v > best) best = v;
  }
  if (!isFinite(best) || best <= 0) return fallback;
  if (Math.abs(best - fallback) > 1.0) return fallback;  // sanity: invalid lap
  return best;
}
```

`annotateSegments` must accept `scoringLastLapTime` as an optional 4th param
and apply `_authDuration` when present.

## Magnitude of error

Bahrain Outer (3510 m, ~71 s laps) measured values from
`session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet`:

| Lap | `max(lap_time_s)` | authoritative (`scoring_last_lap_time_s`) | undercount |
|-----|-------------------|-------------------------------------------|------------|
| 3   | 71.562 s          | 71.679 s                                  | **117 ms** |
| 5   | 71.952 s          | 72.029 s                                  | **77 ms**  |
| 6   | 71.724 s          | 71.900 s                                  | **176 ms** |

When lap 5 is the driver and lap 6 is the reference the `lap_time_delta_s` error
is `(−77) − (−176) = +99 ms` — the driver appears 99 ms faster than they actually
are. With the reference as the best available lap (typically the fastest), this
means the coaching baseline is systematically mis-anchored.

## Root cause

`scoring_last_lap_time_s = scor_v.mLastLapTime` is updated in the **next** lap's
frames after the finish line. The current lap's segment therefore only contains
the value from the **previous** lap. To recover this lap's authoritative time you
must either:

- Look forward into the next segment (Python `_authoritative_duration()` strategy),
- OR read `max(scoring_last_lap_time_s)` within the current segment when it
  matches `max(lap_time_s)` within 1 s — this works for a single-segment
  reference parquet where the value "arrived" early in the segment and the
  segment IS the one whose time we want.

Both strategies are already validated by the bug-10c data and the extract-script
implementation.

## Files to fix

### `product/python/lap_telemetry/parquet_utils.py` (NEW)

Extract shared helper used by both `summary.py` and `lap_comparator.py`:

```python
def authoritative_duration(
    table: pa.Table,
    seg_start: int,
    seg_end: int,
    next_seg_start: int | None,
    next_seg_end: int | None,
) -> float:
    """Authoritative lap duration: scoring_last_lap_time_s from next segment,
    or max(scoring_last_lap_time_s) within this segment, else max(lap_time_s).
    """
    lap_t = table.column("lap_time_s").to_pylist()[seg_start:seg_end]
    fallback = max(lap_t) if lap_t else 0.0

    col_name = "scoring_last_lap_time_s"
    if col_name not in table.schema.names:
        return fallback

    # Try next segment first (standard strategy)
    if next_seg_start is not None:
        vals = [
            v for v in table.column(col_name).to_pylist()[next_seg_start:next_seg_end]
            if v is not None
        ]
        if vals:
            candidate = max(vals)
            if abs(candidate - fallback) <= 1.0:
                return candidate

    # Fallback: try within this segment (for single-segment reference parquets)
    vals = [
        v for v in table.column(col_name).to_pylist()[seg_start:seg_end]
        if v is not None
    ]
    if vals:
        candidate = max(vals)
        if abs(candidate - fallback) <= 1.0:
            return candidate

    return fallback
```

### `product/python/lap_telemetry/summary.py`

Replace `max_lap_t = max(seg_lap_t)` with a call to
`authoritative_duration(t, start_idx, end_idx, next_start, next_end)`.

### `product/python/lap_telemetry/coach/lap_comparator.py`

Replace the two `max(t for t in ... if t > 0)` calls with
`authoritative_duration()`. For the driver lap the next segment is available
in the same session table (since `lap_number` filter was applied to get the
segment but the full table is still in memory). For the reference the
within-segment fallback should suffice.

### `product/web/js/pipeline.js`

Add `_authDuration()` helper and update `annotateSegments()` signature to accept
an optional `scoringLastLapTime` array. Callers in `compare.html` / `main.js`
must pass the loaded `scoring_last_lap_time_s` column.

## Tests to add

### test_authoritative_duration_comparator

Build a synthetic two-segment session table where:
- Segment 1 (lap 5): `max(lap_time_s) = 71.952`, `scoring_last_lap_time_s` in
  segment 2 rows = `72.029`
- Segment 2 (lap 6): `max(lap_time_s) = 71.724`, `scoring_last_lap_time_s` in
  segment 3 rows = `71.900`

Call `compare_laps(session_parquet, ref_parquet, model, lap_number=5)`.
Assert `facts.lap_time_delta_s` uses 72.029 for the driver and the authoritative
value for the reference, not the raw `max(lap_time_s)`.

### test_summary_uses_authoritative_duration

Build the same synthetic table. Call `summary._authoritative_duration()` (or the
shared util) for segment 1. Assert result == 72.029, not 71.952.

### test_ref_single_segment_within_fallback

Build a reference parquet with a SINGLE segment where `scoring_last_lap_time_s`
rows = 71.900 and `max(lap_time_s)` = 71.724. No next segment exists.
Assert `authoritative_duration()` returns 71.900 (within-segment strategy).

### test_invalid_lap_fallback

`scoring_last_lap_time_s` = 71.679 in next segment but `max(lap_time_s)` = 78.883
for the current lap (invalid/slow lap). Assert fallback == 78.883 is returned.

### integration: compare_laps live session

For the Bahrain session (`session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet`):
- Driver = lap 5 → authoritative 72.029 s
- Reference = `reference_lap_session_20260529T092852Z_bahrain-outer-circuit_lmu_seg7.parquet`

Assert `facts.lap_time_delta_s` matches `72.029 − ref_authoritative` to within 0.01 s
(not the raw `max(lap_time_s)` delta).

## Acceptance

- `lap-telemetry summary sessions/session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet`
  shows `1:11.679`, `1:12.029`, `1:11.900` for laps 3, 5, 6 (matching HUD).
- `compare.html` — fastest-lap ★ on lap 5 (72.029 s), not lap 6 (71.900 s appears
  faster by raw `max(lap_time_s)` but is actually slower by the corrected times).
  Wait — check: 72.029 > 71.900 so lap 6 IS faster. The ★ should still correctly
  land on the faster corrected lap; the fix ensures the margin is accurate, not
  inverted.
- `LapComparisonFacts.lap_time_delta_s` is within 10 ms of the true delta
  for any same-session lap pair.
- All existing pytest tests continue to pass.
