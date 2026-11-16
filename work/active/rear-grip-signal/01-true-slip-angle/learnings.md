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

---

# Closure learnings (phase B5–6 + C)

## `mGripFract` is dead in LMU — across every recording, not just one build

The plan listed "does LMU publish `mGripFract`?" as an open question with a
straight-line test as the answer. The answer is in the recordings that were
already on disk: **61 of 61 sessions that carry the column record a constant
`0.0`**. It is not a calibration problem and there is nothing to fix in the
reader — the field exists in the shared-memory struct, it is just never
populated. Recorded, refused, done.

The lesson generalises: **the plan's "record a stint to answer question X"
is often already answerable from the sessions on disk.** Look at the newest
recordings before scheduling driving time. Here the "blocked on the user"
status cost a full slice of delay for a question the data answered in minutes.

## A rear slip angle is `atan2` of the ground velocities, and the gates prove it

The plan's fallback ("if `mGripFract` is dead, rest the slice on the slip angle
alone") is the one that worked, with no schema change: the phase-B4 columns
already carried everything needed. Four independent checks, all green:

- **straight ≈ 0**: median 0.03–0.04° where the legacy channel idled at ±139°.
  This is the check that kills a wrong frame hypothesis.
- **grows with lateral acceleration**, not with steering input: 0.03° / 0.66° /
  1.46° for < 0.3 g / 0.8–1.3 g / > 1.3 g.
- **sign matches the yaw rate** on 99.9% of rotating samples — an independent
  channel agreeing, which the legacy channel could not do (r ≈ 0).
- **a single-lap outlier exists and is the one the driver reported**: 6.51°
  against a 1.7–2.0° envelope, with the brake applied at the apex.

A rear wheel's heading is the car's heading, so `atan2(lat, |lon|)` needs no
`mToe` term: measured straight-line residual is 0.03°, an order of magnitude
below the toe it would correct. **YAGNI: do not add the column.**

## The `braking` window must be a percentile, not a median

First implementation measured `braking_deg` as the *median* slip from entry to
apex while `brake_norm > 0.05`. On the lap that actually slid that returned
2.75° — below the instability threshold — because 70 m of ordinary brake zone
dilutes ten metres of slide. The fact was true and the answer was wrong.

Fixed by taking the **95th percentile over the whole corner zone while the brake
is on** (4.87° on that lap). Rule: a window that contains "before anything
happened" and "when it happened" must be summarised by its tail, not its middle.

## Thresholds have to be relative to the car's own envelope

An absolute "3° is sliding" would fire on a car with more rear slip everywhere
and stay silent on this one at 2.6°. The rule that survived contact with the
data is:

    instability if apex_slip >= max(3.0, 1.5 * median clean-lap apex slip)

with the session's own clean-lap median as the baseline. That flags the 6.51°
lap in a 1.73° session and stays quiet on the 2.05° laps of a 1.76° session.

## `state` names matter more than numbers here

The three states are deliberately not "sliding / gripping / unknown":

- `measured_instability` — a lap above the envelope, cited with segment and lap;
- `no_detected_instability` — valid samples, nothing above the envelope, **and
  the text says it is not a claim that the car is universally stable**;
- `unknown` — and the reason is one of: channel absent, dead ground velocity,
  no sample passing validity, or (importantly) *coverage*: two valid laps out of
  six is unknown, not "no slip". A corner with no clean-lap measurement is
  unknown even if a non-clean lap was measured — with the non-clean observation
  still reported separately.

## Small mechanics

- `session_corner_extras.py` is already past the 437-line ceiling, so the new
  measurement lives in `rear_slip.py` and the oversized file only gained four
  dataclass fields. Do not add logic to it.
- `pyarrow` per-sample Python loops over 148k rows cost ~2 s per session; one
  test that builds full facts on the biggest race fixture is acceptable, but
  keep the physics test to column reads.
- The drill-down block budget is 1500 bytes and Silverstone's corners sit at
  1481–1510 — the rear-stability line must be appended *before* the per-lap
  table or it will be the first thing `_clip` throws away.
