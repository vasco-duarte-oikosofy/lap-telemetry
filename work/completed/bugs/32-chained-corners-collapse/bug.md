# Bug 32 — Chained corners collapse into one: the coach fuses Roggia 1 + 2 and coaches "brake 200 m too early" for the wrong turn

## Symptom

Monza Curva Grande / DKR Engineering LMP3 (P3) practice
`20261101T055404Z`. The coach spoke a note about **Variante della Roggia 2**
claiming the driver **braked ~200 m too early** — physically impossible: the
whole Roggia 2 zone is 78 m long (2131 → 2209 m), so 200 m earlier is *inside*
Roggia 1.

Two symptoms, one root cause:

1. **Roggia 1 is never coached, Roggia 2 gets the note.** Replaying lap 7 of
   that session through `CornerExitDetector` yields
   `t1 Curva Grande 1795 → t3 Variante della Roggia 2 2209 → t5 Lesmo 2 2855 …`.
   `t2` and `t4` never fire, and Ascari 2/3 collapse too (only `t7` fires).
2. **The Roggia 2 entry fact is measured inside Roggia 1.** Full-lap facts on
   laps 3, 6, 8, 12, 13 of that session:

   ```
   t3 Variante della Roggia 2  entry  drv=1931 m  ref=2135 m  delta=+204 m  loss=+0.156/+0.159/+0.557/+0.285/+0.184 s
   ```

   1931 m is exactly `s_start_m - look_back_m` for Roggia 2
   (2131 − 200) and sits on Roggia 1's brake point. The same defect produces
   `t9 Variante Ascari 3  drv=4104 m  ref=3984 m  delta=-120 m` on laps 2, 3,
   5, 8, 14 (the *reference* entry stolen into Ascari 2).

## Root cause

The Monza model has **no gap** between chained turns:
`Roggia 1.s_end_m = 2130`, `Roggia 2.s_start_m = 2131` (same for
`Ascari 1/2` at 3953/3954 and `Ascari 2/3` at 4062/4064). Every consumer treats
a corner as an isolated island with fixed ±windows:

1. `CornerExitDetector.feed()` only emits when
   `model.get_corner_at(distance)` returns `None`. With 2130/2131 contiguous
   that never happens, so `_current_corner_id` is silently overwritten by the
   next chained corner — **Roggia 1 is swallowed**.

2. `find_entry_point()` looks back a fixed `look_back_m = 200` from
   `s_start_m`, ignoring the previous corner. For Roggia 2 the window starts at
   1931 m, inside Roggia 1's braking zone. If the driver's throttle pickup
   between the two turns peaks **below 0.9** (lap 8: 0.73), the code finds no
   `throttle_lift` of its own and falls back to `speed_peak` — the *fastest*
   point in the window, which is Roggia 1's braking zone at the window start.
   The reference (which does reach 1.0 at 2127 m) reports 2135 m → delta
   **+204 m**: "you braked 200 m too early for Roggia 2".

3. `find_exit_points()` searches `s_end_m + 50 m`, so Roggia 1's *exit* is
   measured 2158–2175 m — inside Roggia 2 (lap 8: `t2 exit phase_d=2158`).

## Reproduction

```bash
export PATH=".venv/Scripts:$PATH" PYTHONUTF8=1 PYTHONPATH=product/python
python3 - <<'PY'
from pathlib import Path
from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.lap_comparator import compare_laps
model = load_track_coaching_model(Path(
    "product/data/track-coaching/monza-curva-grande-circuit_dkr-engineering-4-elms25.json"))
ref = Path("product/data/reference-laps/"
           "monza-curva-grande-circuit_dkr-engineering-4-elms25_time_01.35.182.parquet")
sess = Path("sessions/session_20261101T055404Z_monza-curva-grande-circuit_lmu_practice.parquet")
for lap in (3, 6, 8, 12, 13):
    f = compare_laps(sess, ref, model, lap_number=lap, top_n=60)
    for c in f.top_losses + f.top_gains:
        if c.corner_id == "t3" and c.phase == "entry":
            print(lap, c.corner_id, "drv_entry=%.0f" % c.phase_distance_m,
                  "ref_entry=%.0f" % c.reference_phase_distance_m,
                  "delta=%+.0f" % c.entry_distance_delta_m)
PY
```

Current output: `+204` on every listed lap. A replay of `CornerExitDetector`
over lap 7 prints a single `t3` event and no `t2` event.

## Fix direction

Bound every phase window by the neighbouring corner of the *same model*, and
let the exit detector emit at a chained boundary:

- `find_entry_point(..., min_distance_m=prev.s_end_m)` — entry may never start
  before the previous corner ends.
- `find_exit_points(..., max_distance_m=next.s_start_m)` — exit may never reach
  into the next corner. Falls back to `s_end_m`, which is the chained boundary.
- `lap_comparator` passes both bounds (driver *and* reference, and
  `find_straight_end_after_corner`).
- `CornerExitDetector` emits a `CornerExited` for the *previous* corner when
  `get_corner_at()` hands over to a chained neighbour, and the anti-chatter
  cooldown becomes per-corner so Roggia 2's note is not swallowed by Roggia 1's
  ~3 s earlier.

## Files

- `product/python/lap_telemetry/coach/entry_detection.py`
- `product/python/lap_telemetry/coach/exit_detection.py`
- `product/python/lap_telemetry/coach/lap_comparator.py`
- `product/python/lap_telemetry/coach/corner_exit_detector.py`
- `dev/scripts/test_bug32_chained_corners.py` (new regression test)

## Status

✅ Fixed in `8e0e2e5`, docs in `7fa6356` — user confirmed after a live session; moved to `work/completed/bugs/`.

Regression test: `dev/scripts/test_bug32_chained_corners.py` (feature list `bug32-chained-corners`).
