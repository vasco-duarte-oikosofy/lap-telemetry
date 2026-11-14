# Learnings — Slice 01 (true slip angle / verified refusal)

## What the recorded channel physically is (proved, with numbers)

`slip_angle_*_deg` is `degrees(atan2(mLateralPatchVel, mLongitudinalPatchVel))`
(`recorder/connect.py::_slip_deg`) — two contact-patch velocities expressed in
the car frame. Measured on three committed sessions
(`artifacts/slip-spike.txt`):

| session | corr(slip_rl, steering_norm) | slope k (deg per steering unit) | residual after removing k·steering | straight-line reading |
|---|---:|---:|---|---|
| Barcelona race 2026-11-13 (the trigger session) | **+0.52** | +369 | corr 0.000, spread **1068°** | +139° |
| Silverstone National practice 2026-11-11 | +0.40 | +302 | corr 0.000, spread 573° | +171° |
| Imola 2026-05-17 (older schema) | +0.39 | +246 | corr 0.000, spread 378° | — |

Three independent facts, each fatal on its own:

1. **It follows steering, not lateral load.** One linear steering term explains
   the entire steering correlation (residual corr = 0.000 on all three
   sessions), with a slope of 250–490° per unit steering — i.e. the value is
   re-wrapped many times across a normal lock range. A physical slip angle has
   no such gain.
2. **It reads ±180° on a straight.** On the Wellington Straight at 203 km/h the
   rear-left channel medians **+170.6°** (70 % of samples within 20° of ±180°,
   and a stable 1 % sample-to-sample jump rate — this is not noise). A real car
   sideslip angle there is ~0°. `atan2` of two near-zero velocities does exactly
   this: it parks at ±180° and only moves when the tiny inputs change sign.
3. **It carries no yaw information.** Yaw rate derived independently from a
   central difference of `pos_x/pos_z` correlates with `d(slip_rl)/dt` at
   **−0.01, −0.01, −0.07** across the three sessions, while that estimate itself
   spans ±15 deg/s — plenty of real signal for the channel to have matched.

So the channel is a *direction of travel in the car frame*, dominated by the
input and dead near zero speed — not a tyre slip angle, and not the car's
sideslip angle either (fact 2 rules that out).

## Why no post-processing can rescue it

Recovering a slip angle needs the wheel's own heading: road-wheel angle (whose
gain is car-specific and not recorded) or wheel ground velocity. Differencing
`pos_*` gives the *car's* heading, and the angle between car heading and car
velocity is car sideslip — a different quantity from tyre slip, and unobservable
here anyway because the recorded pair is near-zero on straights.

The `recorded − k·steering` reconstruction is a *mechanism test*, not a
measurement: it removes the steering dependence at any k you choose, so it can
never be validated against anything independent. Shipping it would violate the
slice's own non-goal. **Not measurable from the current schema** — recorded as
such.

## The refusal now names the mechanism

```
the sim value is atan2 of two contact-patch velocities in the car frame, so it
idles at ±180° on a straight and follows steering input (r=+0.52); a tyre slip
angle needs the wheel's own heading, and no wheel heading is recorded
```

Two existing assertions pinned the *old* wording (`"wrap" in reasons` in
`test_session_corner_extras.py` and `test_session_report.py`) and had to change
with it. That is the intended cost of making a refusal specific: the reason
string is a product surface, not a log line.

## Recording the physics instead — what went into the schema

`LMUWheel` (vendored header) already exposes everything needed; the recorder
just never stored it. Seven **nullable** columns now ship:

| column | sim field | why |
|---|---|---|
| `grip_fraction_rl/_rr` | `mWheels[2/3].mGripFract` | "fraction of the contact patch that is sliding" — the direct answer to *was the rear sliding* |
| `wheel_ground_vel_lat/lon_rl/_rr` | `mWheels[2/3].m{Lateral,Longitudinal}GroundVel` | rear slip angle: a rear wheel's heading is the car's heading (toe is the only correction) |
| `yaw_rate_radps` | `mLocalRot.y` | independent cross-check (rF2/LMU local axes: y = up, so y = yaw) |

Three decisions worth remembering:

- **Nullable, never 0.0.** `_wheel_float` maps a missing field *and* a NaN to
  `None`; a fabricated `0.0` in `grip_fraction_rl` would read as "not sliding"
  in every debrief of that session. This is the same trap the `abs_active` /
  `tc_active` columns documented.
- **Raw sim fields only.** No transformation in the reader, so the validation
  gate can still reject the frame hypothesis without a schema migration.
- **The yaw axis is an assumption, stated as one.** `mLocalRot.y` is yaw under
  rF2's x-right / y-up / z-forward convention; the calibration gate must confirm
  sign and magnitude against the position-derived estimate before any product
  surface trusts it.

## What is still unvalidated (do not consume these columns yet)

Nothing in `session_corner_extras`, the priorities or the drill-down reads the
new columns. The gates in `plan.md` phase B step 6 need a **recording made after
this commit**: straight (grip < 0.05, rear slip ≈ 0°), clean hairpin (2–6°),
Repsol with the brake held (slip ≥ clean value *and* grip rising through the
apex), plus the yaw-rate sign check. If the straight-line case is not near zero,
the frame hypothesis is wrong and the columns stay unread — the refusal remains
the honest answer.

`mGripFract` may be dead (some builds report 0.0 always); that is gate one, and
the slice degrades to slip angle only if so.
