# Bug 21 — Lap duration inconsistency across the codebase

## Symptom

The same lap shows different times in different parts of the app and tooling:

- `lap-telemetry summary` shows 1:32.367 for lap 16
- `compare.html` legend shows 1:32.193 for the same lap
- The reference lap export named the file `_time_01.31.770` (a phantom fast lap caused by the same root cause)

## Root cause

`lap_time_s` = `mCurrentET − mLapStartET` — the sim's elapsed-time counter for the current lap. At the lap crossing, `mLapStartET` resets for the new lap before all frames for the **outgoing** lap are recorded. The last ~0.3–0.6 s of the outgoing lap are therefore lost, and `max(lap_time_s)` systematically undercounts completed lap times.

The correct source is `scoring_last_lap_time_s` = `mLastLapTime` from the sim's scorer, which propagates into the **next** lap's frames and carries the officially scored lap time. `authoritative_duration` (Python) and `authDuration` (JS `pipeline.js`) both implement the same logic: prefer `scoring_last_lap_time_s` from the next segment, fall back to `max(lap_time_s)` when the scorer value is absent or implausible (>1 s deviation).

## Sites audited

| Site | Uses authoritative duration? | Status |
|---|---|---|
| `lap-telemetry summary` | ✅ `authoritative_duration` | Correct |
| `annotateSegments` / picker dropdown | ✅ `authDuration` via `seg.duration` | Correct |
| `export_fastest_reference_laps.py` | ❌ `max(lap_time_s)` | **Fixed 2026-06-06** |
| `formatPickLabel` (legend labels in compare.html) | ❌ `max(lap_time_s)` inline | **Fixed 2026-06-06** |
| `lap_comparator.py` (coach) | ✅ `authoritative_duration` | Correct |

## Fixes applied (2026-06-06)

### `dev/scripts/export_fastest_reference_laps.py`
Replaced `find_complete_laps` (which used `max(lap_time_s)`) with `build_segments` + `authoritative_duration`. This also fixed the fastest-lap selection: lap 19 at 91.770 s was a phantom caused by the undercount; the true fastest lap is 16 at 92.367 s.

### `product/web/js/utils.js` — `formatPickLabel`
Was recomputing duration as `max(lap_time_s)` from the raw column. Now reads `seg.duration`, which is already set to the authoritative value by `annotateSegments`.

## Remaining risk

Any new code that reads `lap_time_s` directly to derive a lap time (rather than going through `seg.duration` in JS or `authoritative_duration` in Python) will reintroduce this undercount. The correct pattern:

- **Python**: `from lap_telemetry.parquet_utils import authoritative_duration, build_segments`
- **JS**: use `seg.duration` (set by `annotateSegments`) — never slice `lap_time_s` and take `max` directly

## How to verify

```
lap-telemetry summary sessions/session_20260606T064918Z_autdromo-jos-carlos-pace_lmu_practice.parquet
```
Fastest clean lap should be 1:32.367 (lap 16). `compare.html` legend should show the same time after loading that session and selecting lap 16.
