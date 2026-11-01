# Learnings — Bug 32: chained corners must not collapse

## What surprised me

- **The phantom was a `speed_peak` fallback, not a `throttle_lift`.** I assumed
  the driver's entry was taken from the first throttle lift in the 200 m
  look-back window. It is not, on the laps where it bit: the driver's throttle
  never reaches 0.9 between Roggia 1 and Roggia 2 (lap 8 peaks at 0.73), so
  `find_entry_point` finds **no** lift at all and falls back to "the speed local
  maximum in the window" — and the window starts at Roggia 1's brake point,
  which is by construction the fastest point in it. Bounding the window fixes
  both code paths; bounding only the `throttle_lift` branch would not have
  fixed anything.
- **The bug is a driver/telemetry coincidence, so it looks intermittent.** Laps
  4, 5, 7, 9 were clean (entry 2132–2138 m) and laps 3, 6, 8, 12, 13 were
  phantom — the difference is only whether the throttle pickup between the two
  Roggias crosses 0.9. That makes it easy to dismiss as "the model is fine".
- **The reference was also being stolen, in the other direction.** `t9 Ascari 3`
  reported `drv=4104 ref=3984` on 5 laps: the *reference*'s entry was inside
  Ascari 2's zone. Any fix has to bound the reference search too — bounding only
  the driver would have left a −120 m phantom.
- **Barcelona has the same defect**, which nobody had noticed: `t7 "Turn 8"`
  ends at 2850 m and `t8 "Turn 9 – Campsa"` starts at 2851 m. The existing
  `test_entry_gain_swap_barcelona` guard (`delta-t gain < speed/100 heuristic`)
  started failing purely because Campsa's entry window shrank from 200 m to 73 m
  — the guard implicitly assumed a free 200 m window. Excluding clamped windows
  (documented inline) keeps the guard meaningful for the corners it was written
  for; I did not weaken the assertion itself.
- **The 1 m gap is enough for a handover but not for an exit.** `Ascari 2 → 3`
  has a 2 m gap (4062/4064), so the old "outside all corners" path *does* fire
  there for Ascari 2. Only the truly touching pairs (1 m gaps: Roggia 1/2 and
  Ascari 1/2) needed the new handover path. Both paths now share `_emit()`.

## Things the next agent needs to know that are not in the spec

- **`compare_laps` on a partial lap is a dead end.** The `< 80 % of lap_length`
  coverage guard (`PartialLapError`) makes `LiveCornerFactGenerator` return
  `None` for *every* corner exit on a 5.7 km track — its window is
  `exit + 150 m`. So on Monza Curva Grande the driver only ever hears the
  after-lap summary. The corner-exit code path looks alive but is silent.
  That is why "before/after" on the real session is best demonstrated through
  the lap summary, not through `LiveCornerFactGenerator`.
- **`track_model.get_corner_at()` returns the first matching corner**, and the
  curated Monza/Barcelona models have zero-length gaps between chained turns.
  Any code that assumes "no corner ⇒ corner finished" is wrong for those
  models. Grep for `get_corner_at` if you change the detector again.
- **Cooldown is still global (8 s).** On Monza that means Roggia 1's handover at
  2130 m is dropped (Curva Grande exited 6 s earlier at 1795 m). Fixing that is
  a speech-pacing decision, deliberately left out of this bug — see
  `handoff.md` deferred item 1.
- **Test data:** no recorded session is needed for this bug class; a synthetic
  3 km lap (1 m grid, `lap_time_s` integrated as `Σ 3.6 / speed`) is enough and
  runs in milliseconds. `dev/scripts/test_bug32_chained_corners.py` shows the
  recipe, including the `pyarrow` table shape `compare_laps` needs
  (`lap_number, lap_time_s, lap_distance_m, speed_kph, throttle_norm,
  brake_norm, session_time_s`).
- **Reproducing "before" without reverting:** `git archive HEAD product/python
  product/web/js | tar -x -C <tmp>` gives you the old package to run behind
  `PYTHONPATH`; it needs `dev/scripts/compute_delta_t.mjs` and `product/web/js/`
  alongside it or `js_pipeline` throws `FileNotFoundError`.
- **The suite must run with the venv on PATH** (`export PATH=".venv/Scripts:$PATH"
  PYTHONUTF8=1`); without it every `python3` wrapper dies with the Microsoft
  Store stub (exit 9009) and the "failures" are pure noise.
