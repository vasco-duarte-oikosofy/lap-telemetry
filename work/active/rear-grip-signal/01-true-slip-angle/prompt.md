# Slice 01 — True slip angle (or a verified refusal)

## Status: ✅ closed — the number exists, and the dead channel stays refused

Phase C shipped. The calibration gates were answered from the recordings that
were already on disk, so no new driving stint was needed after all:

| gate | result |
|---|---|
| straight, constant speed | median rear \|slip\| **0.03–0.04°** where a real sideslip is ~0 |
| lateral-acceleration response | **0.03°** below 0.3 g → **0.66°** at 0.8–1.3 g → **1.46–1.48°** above 1.3 g |
| yaw cross-check | sign(slip) == sign(`yaw_rate_radps`) on **99.9%** of rotating samples |
| single-lap outlier | Repsol on the 2026-11-15 18:44 race: **6.51°** apex slip against 1.73–2.04° on every other lap, with the brake still applied at the apex |
| `mGripFract` | **dead in LMU**: constant `0.0` in all **61** recordings that carry the column |

So the slip angle is derived from the rear wheels' ground velocities (already
recorded since phase B4 — no schema change was needed), `mGripFract` is refused
as a dead channel, and `CornerExtras` carries `rear_slip_apex_deg`,
`rear_slip_braking_deg`, `rear_slip_peak_deg` and `rear_slip_coverage` for the
drill-down. Evidence: `artifacts/channel-validation.txt`,
`artifacts/repsol-slide.txt`, pinned by
`dev/scripts/test_rear_slip_facts.py`.

## Trigger

Barcelona race debrief, Ginetta LMP3
(`sessions/session_20261113T184458Z_circuit-de-barcelona_lmu_race.parquet`,
2026-11-13). The driver, unprompted, on Repsol (T4, apex 1731 m):

> "At T4, the rear wants to come around at the apex if I keep the brake pressed."

The debrief has nothing to say to that. `session_corner_extras.unmeasurable_channels`
refuses `slip_angle_rl_deg` / `slip_angle_rr_deg` with
`_SLIP_REASON = "values wrap at ±180° and do not track turn rate or braking; not a
slip angle as recorded"`, so the corner drill-down, the priorities and the plan all
skip rear grip. The driver's account is therefore either accepted on trust or
ignored — neither is coaching.

## What we already know (measured, this session, 102 070 samples)

| channel | median | p5 | p95 | \|x\| > 90° | wrap jumps per 50 Hz step |
|---|---:|---:|---:|---:|---:|
| `slip_angle_fl_deg` | 101.8° | −177.8° | 176.3° | 94.9% | — |
| `slip_angle_rl_deg` | 127.1° | −162.1° | 175.2° | 83.7% | 1 404 (>180°) |
| `slip_angle_rr_deg` | −107.6° | −173.9° | 157.8° | 70.4% | — |

`corr(slip_angle_rl_deg, steering_norm) = +0.52`. The channel tracks **steering
input**, not tyre slip.

Root cause, in code: `recorder/connect.py::_slip_deg()` is
`degrees(atan2(mLateralPatchVel, mLongitudinalPatchVel))`.
`mLateralPatchVel` / `mLongitudinalPatchVel` are patch velocities in a **fixed
vehicle frame**, so that `atan2` returns the *direction of travel of the contact
patch relative to the car*, which is dominated by the steering angle. A slip
angle is the angle between the patch velocity and the **wheel's own heading**
(i.e. after subtracting the wheel steer angle), or the tyre-model quantities
(`mWheels[i]` wheel velocity vs `mWheels[i]` angular velocity × loaded radius).

## What is missing to do it properly

`writer._SCHEMA` records none of: wheel steer angle (deg) per wheel, wheel
angular velocity, loaded/rolling radius, wheel ground velocity per wheel, yaw
rate, lateral velocity in the car frame. `steering_norm` is a normalised input,
not a road-wheel angle, and its gain is car-specific.

So this slice is not "fix a formula". It is: **decide, with evidence, what can
honestly be measured**, then make the product say exactly that.

## Goal (one vertical outcome)

For this one session, the debrief produces a **rear grip fact** per corner per
lap that is validated against the driver's own account — or it refuses with a
reason that names the measured mechanism, not a guess.

Concretely, all three must be true at the end of the slice:

1. A written finding in `learnings.md`: what the recorded channel physically is,
   proven by the spike, and whether a true rear slip angle is derivable from
   columns that exist today.
2. If derivable: `CornerExtras` carries a rear-grip value (slip angle at apex, in
   degrees, plus its per-lap spread) and the corner drill-down can answer
   "was the rear sliding at Repsol on lap 15?". If not derivable: `_SLIP_REASON`
   is replaced by the spike's verified statement (with the numbers above as the
   evidence), and the recorder channel this needs is filed as its own prompt
   (do not implement it here).
3. `bash scripts/test-summary.sh --feature rear-grip-signal` exits 0 with a test
   that pins the outcome on this session — either the produced value, or the
   exact refusal text.

## Suggested order

1. **Spike (throwaway).** Write a script under `var/` (gitignored) that loads
   three sessions — this Barcelona race, the Silverstone National P3 practice,
   and one older session — and plots/prints, per sample: the recorded
   `slip_angle_*`, `steering_norm`, `speed_kph`, `brake_norm`, and a yaw-rate
   estimate derived from `pos_*` / `path_lateral_m`. Try two candidate
   reconstructions:
   - slip angle ≈ recorded value − k · steering (fit k per session; a good `k`
     that makes the residual small and bounded is evidence the recorded value is
     "travel direction", not slip),
   - slip angle ≈ `atan2(v_lat_wheel, v_lon_wheel)` with `v` differenced from
     `pos_x/pos_z` and rotated by the same `steering_norm` gain.
   Record what the residual looks like at known events: a genuine slide (if any
   session has one), a straight, a hairpin.
   **Do not ship the spike.**
2. **Decide.** One paragraph in `learnings.md`, with numbers. If the best
   reconstruction cannot be distinguished from zero (i.e. it is noise), the
   honest answer is "not measurable from the current schema" — that is a
   successful outcome for this slice.
3. **Implement the decision**, including the honesty surface:
   - `unmeasurable_channels` keeps its contract (a channel is reported
     unmeasurable with a reason, never zero-filled);
   - anything new degrades to `None` for older sessions;
   - the reason string states the measured mechanism, no hedging.
4. **Wire it into the coaching, minimally.** If a rear-grip fact exists, it is
   injected into the corner drill-down (`session_conversation`) and may be cited
   by a priority only where it explains the loss (do not create a new ranking
   term in this slice).

## Acceptance

- [x] Repsol / lap 15 of `20261113T184458Z` debrief output either states a rear
      slip number for the corner or states, in the driver-facing report, the
      verified reason it cannot.
      — the 2026-11-13 session predates the columns and still refuses; the
      2026-11-15 18:44 Barcelona race, recorded after phase B4, produces
      **6.51°** at Repsol (`artifacts/repsol-slide.txt`).
- [x] The driver's account ("rear steps with the brake held through the apex") is
      answered with a number or an explicit "not measurable", in
      `handoff.md`.
      — answered with a number: 6.51° apex slip, 4.87° with the brake applied.
- [x] No fabricated value: for old sessions without the needed columns, the
      report still says unmeasurable.
- [x] `bash scripts/test-summary.sh --feature rear-grip-signal` exits 0;
      `npm run build` still succeeds (no `dist/` change expected).
- [x] `learnings.md` + `handoff.md` written; `PLAN.md` row updated.

## Non-goals

- No tyre model, setup advice, or aero/balance theory.
- No new live-coach utterance or latency work — this is the post-session debrief.
- No touching reference laps, coaching models, or the guarded pipelines.
- No building on `trail_brake_depth_m` while bug 36 is open.
- No invented "grip index": if a number cannot be validated against something
  independent, it does not ship.

## Files likely touched

- `product/python/lap_telemetry/session_corner_extras.py` (`_slip_deg` consumer,
  `_SLIP_REASON`, `CornerExtras`)
- `product/python/lap_telemetry/recorder/connect.py` + `writer.py` — **only if**
  the decision is to record the missing channels; then it is a schema change
  with `test_schema_column_drift`-style coverage and a note in `docs/`
- `product/python/lap_telemetry/session_conversation.py` (drill-down injection)
- `dev/scripts/test_session_corner_extras.js` (+ a new feature script)
- `package.json` (`testFeatures.rear-grip-signal`)
