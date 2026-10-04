# Bug 28 — Lap duration must come from the telemetry lap-start clock

## Symptom

`lap-telemetry summary` reported Road Atlanta lap 15 as **1:17.345**, and that
wrong value propagated into the reference-lap filename, the coaching model,
and the compare viewer. The in-game best is **1:16.809** (TinyPedal's recorded
delta-best is 76.80896).

## Root cause

The authoritative-duration helpers preferred the sim scorer's `mLastLapTime`
(`scoring_last_lap_time_s`), which **lags one lap** on Road Atlanta: during
lap 16 the scorer still held lap 14's time (77.345). `max(lap_time_s)` is
closer but shorts the last partial sample by ~0.1 s.

TinyPedal derives the lap from consecutive **telemetry** lap-start ETs
(`lmuTeleVeh.mLapStartET`), not the scorer. Our recorder already stores
`session_time_s - lap_time_s == mLapStartET`, so the same value is recoverable
with no schema change.

## Execution order

1. **Test-first (Python).** `dev/scripts/test_lap_duration_telemetry.py`:
   synthetic two-segment table with a stale scorer; real Road Atlanta lap 15 =
   76.809; real Paul Ricard lap 4 = 96.804; explicit `authoritative_lap_time_s`
   metadata override.
2. **Fix the shared helper.** `product/python/lap_telemetry/parquet_utils.py`
   `authoritative_duration` priority: schema metadata → telemetry lap-start
   diff → legacy scorer → `max(lap_time_s)`.
3. **Fix the web helper.** `product/web/js/pipeline.js` `authDuration` mirrors
   the same priority; `annotateSegments` takes `sessionTimes`; `ui.js` loads
   `session_time_s` and passes it.
4. **Record the exact duration.** `export_fastest_reference_laps.py` writes
   `authoritative_lap_time_s` into the extracted parquet's schema metadata.
5. **Align tooling.** `validate_reference_laps.py` provenance loads
   `session_time_s`; `extract_reference_lap.py` delegates to the shared helper;
   `lap_comparator` and `summary` inherit the fix.
6. **Re-export Road Atlanta** and refresh the coaching model
   (`update_reference_and_coaching_model.py`).
7. **Test every product surface** (see Acceptance).

## Acceptance

- `authoritative_duration` and `authDuration` return 76.809 for the practice
  lap and 76.304 for the current race reference.
- **Recorder output contract:** for recorded sessions, `session_time_s - lap_time_s`
  is constant within each completed lap (< 0.01 s spread), so the telemetry
  clock is recoverable from the parquet.
- **Python pipeline:** `summary.run()` prints `1:16.304` for the race lap 15.
- **Export:** `find_complete_laps()` selects race lap 15 @ 76.304 and rejects
  the restart-truncated 1:15.994 lap.
- **Coach:** `compare_laps()` duration deltas are computed from the telemetry
  clock (lap 21 vs ref = +0.113 s).
- **dist/compare.html:** the built bundle's session and reference pickers show
  `1:16.304`.
- `validate_reference_laps.py`: 26 refs, 0 failures.
- `python3`/node tests green; `npm run build` current.

## Notes

- Paul Ricard quali lap 4 agrees between scorer and telemetry (96.804), which
  is why the old scorer-first logic looked correct and why bug 13's synthetic
  fixtures (no `session_time_s`) still pass through the legacy fallback.
- Files: `dev/scripts/test_lap_duration_telemetry.{py,js}`,
  `dev/scripts/test_reference_lap_duration.js`, plus the surface test added in
  this slice.
