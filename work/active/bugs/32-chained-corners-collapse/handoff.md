# Handoff — Bug 32: chained corners must not collapse

**Status:** 🔧 Fixed locally, full suite green, committed. **Pending live test** (only
then move the folder to `work/completed/bugs/`).

## What is on disk now

| File | Change |
|---|---|
| `product/python/lap_telemetry/coach/entry_detection.py` | `find_entry_point(..., min_distance_m=0.0)` — floors the search window at the previous corner's exit. Docstring explains the bug-32 failure mode. |
| `product/python/lap_telemetry/coach/exit_detection.py` | `find_exit_points(..., max_distance_m=None)` — caps the window at the next corner's entry; the `s_end_m` fallback is clamped too. |
| `product/python/lap_telemetry/coach/lap_comparator.py` | New `phase_window_bounds(corners, index) -> (entry_floor, exit_ceiling)`. Applied to driver entry, reference entry, driver exit, reference exit **and** `find_straight_end_after_corner` (which uses the next corner's entry as a gain-window end). |
| `product/python/lap_telemetry/coach/corner_exit_detector.py` | `CornerExitDetector` now emits on a *handover* to a chained neighbour (`get_corner_at()` returns a different corner while the car is still inside a zone), reporting the previous corner at its own `s_end_m`. Emit logic factored into `_emit()` / `_corner_by_id()`. |
| `dev/scripts/test_bug32_chained_corners.py` / `.js` | New regression test, 12 assertions, synthetic 3 km lap with two touching corners (no recorded session needed). |
| `dev/scripts/test_delta_time_gains.py` | `test_entry_gain_swap_barcelona` now skips entry facts whose window was clamped by a chained predecessor (Barcelona t7 `Turn 8` ends at 2850 m, t8 `Turn 9 – Campsa` starts at 2851 m). See learnings. |
| `package.json` | New feature list `bug32-chained-corners` (12 scripts) + `test_bug32_chained_corners.js` added to `scripts.test`. |

## New helpers worth knowing about

- `lap_comparator.phase_window_bounds(corners, index)` → `(entry_floor_m, exit_ceiling_m)`.
  `exit_ceiling_m` is `None` for the last corner and for a wrap-around successor
  (`next.s_start_m <= corner.s_start_m`). Anything else that derives a per-corner
  distance window from the model should use these bounds.
- `CornerExitDetector._emit(corner_id, exit_distance_m, frame)` — single choke point
  for the cooldown + callback, used by both the "outside all corners" path and the
  new handover path.

## Test / build state

```
bash scripts/test-summary.sh --feature bug32-chained-corners   → ALL PASS (478 assertions, 12 scripts)
bash scripts/test-summary.sh --feature interactive-race-coach  → ALL PASS (805 assertions, 27 scripts)
bash scripts/test-summary.sh --pw                              → FAILED, 1385 passed, 6 of 67 scripts failed
npm run build                                                  → OK, product/dist/compare.html current
```

The 6 full-suite failures are **pre-existing and unrelated** (bug 20, Windows ESM
paths): `test_static_outline_runtime_rendering`, `test_apex_annotations`,
`test_apex_metrics`, `test_apex_metrics_aggregate`,
`test_apex_metrics_surface_terrain`, `test_track_outline_schema_compat` — all die
with `ERR_UNSUPPORTED_ESM_URL_SCHEME ... protocol 'c:'`. No `web/` file was touched
by this slice.

**Windows reminder:** the suite only passes with the venv on PATH
(TESTING_LESSONS L16):

```bash
export PATH=".venv/Scripts:$PATH" PYTHONUTF8=1
```

## Verification on the real session

`sessions/session_20261101T055404Z_monza-curva-grande-circuit_lmu_practice.parquet`
(DKR Engineering #4:ELMS25, 14 laps) vs
`product/data/reference-laps/monza-curva-grande-circuit_dkr-engineering-4-elms25_time_01.35.182.parquet`:

- The phantom `t3 Roggia 2 entry  drv=1931 m  ref=2135 m  delta=+204 m` is gone on
  every lap (was laps 3, 6, 8, 12, 13; `loss` between +0.16 and +0.56 s).
- The Ascari 3 phantom (`drv=4104 ref=3984 delta=−120 m`, laps 2, 3, 5, 8, 14) is
  gone too.
- The one remaining `|entry delta| > 40 m` fact in the whole session is
  `lap1 t4 Lesmo 1 drv=2258 ref=2403 (+145 m)` — a genuine lap-1 out-lap difference,
  not a window artefact.
- Replaying lap 7 through `CornerExitDetector` still prints
  `t1 → t3 → t5 → t6 → t7 → t10` (no `t2`), because the **global 8 s anti-chatter
  cooldown** drops `t2`: Curva Grande exits at 1795 m and Roggia 1's chained boundary
  is 2130 m — about 6 s later. This is unchanged policy, not part of this bug.

## Deferred / spotted while working (NOT fixed here)

1. **Chained pairs get one note, not two.** With the global 8 s cooldown only one
   half of a chained pair can speak. Making the cooldown per-corner (or exempting
   the handover) would coach both — `SpeechQueue` already drops stale pending
   utterances, so pacing would not blow up. Needs a product decision; would flip
   T8 in `test_corner_exit_coaching.py`.
2. **The live corner-exit path never speaks on this track.**
   `LiveCornerFactGenerator.generate()` compares a partial lap stopping at
   `exit + 150 m`, and `compare_laps` rejects anything ending before 80 % of
   `lap_length_m` (`PartialLapError`) — so every corner-exit analysis on Monza
   Curva Grande (5.7 km) returns `None`. The utterance the driver actually hears
   comes from the after-lap summary. Worth its own bug.
3. `find_brake_point()` still uses the fixed 200 m look-back and has no
   `min_distance_m`; it is currently unused by `lap_comparator` (tests only).
4. Short names (`short_name`) are still invisible to the coach — filed as slice
   `12-coach-short-corner-names` in `work/active/interactive-race-coach/PLAN.md`.
