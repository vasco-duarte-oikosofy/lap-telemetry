# Slice 01 — execution plan (develop on the recording machine)

Planning only. Nothing in this folder has been implemented; no production code was
touched. Derived from `prompt.md`, `PLAN.md`, the vendored sim headers and the
schema as it exists at `e49a680`.

## What the evidence already settles

**The recorded `slip_angle_*` column cannot be repaired after the fact.** It is
`atan2(mLateralPatchVel, mLongitudinalPatchVel)` (`recorder/connect.py::_slip_deg`),
i.e. two velocities measured in the car frame, so the angle is dominated by
travel direction, not by tyre slip. The reported session shows it: median |x| >
90° on 70–95% of samples, 1 404 wrap jumps, `corr(slip_angle_rl_deg, steering_norm)
= +0.52`. No post-processing recovers slip from it.

**A true slip angle is not derivable from the recorded columns either.** The
reported parquet (and every session on disk) carries
`slip_angle_{fl,fr,rl,rr}_deg`, `steering_norm`, `speed_kph`, `brake_norm`,
`pos_x/y/z`, `path_lateral_m` — and nothing that pins the car's *heading*: no yaw
rate, no wheel ground velocity, no wheel rotation, no road-wheel angle. Heading
is what separates "the car is travelling sideways" from "the car is turning", so
no arithmetic over these columns yields a slip angle. The one candidate that does
not need heading (fit `k`, take `recorded − k·steering`) is a *mechanism test*,
not a measurement: it has no independent ground truth, so it cannot ship a number
under this slice's own non-goal ("no value that cannot be validated against
something independent").

Conclusion: **slice 01 is a recorder slice with an analysis tail.** The number
comes from columns that do not exist yet; the honest refusal gets sharper now.

## What the sim can give us (vendored headers, `vendor/pyLMUSharedMemory/lmu_type.py`)

`LMUWheel` already exposes, per wheel and unrecorded today:

| field | use |
|---|---|
| `mGripFract` | "fraction of the contact patch that is sliding" (`InternalsPlugin.hpp`) — the direct answer to "was the rear sliding" |
| `mLateralGroundVel`, `mLongitudinalGroundVel` | ground velocity; rear slip angle ≈ `atan2(lat, abs(lon))` because a rear wheel's heading is the car's heading (toe is the only correction, and `mToe` is also exposed) |
| `mRotation` | rad/s, wheel speed — only needed if we want slip *ratio*; **out of scope** (YAGNI) |
| `mToe` | rear-wheel heading correction for the point above |

And `LMUVehicleTelemetry.mLocalRot` (car-frame angular velocity) gives yaw rate,
which is the independent cross-check for any slip-angle number.

Two columns carry the slice: `grip_fraction_rl/rr` (primary) and
`wheel_ground_vel_lat/lon_rl/rr` (the slip angle the driver's sentence is about).
`yaw_rate_radps` is the cheap validation channel. Front wheels are **not** in
scope: they need a road-wheel steering angle whose gain is car-specific, and the
driver's question was about the rear.

## Phases

### A — offline, any machine (no sim)

1. **Spike, throwaway, `var/` (gitignored).** On
   `sessions/session_20261113T184458Z_circuit-de-barcelona_lmu_race.parquet`
   (recorded on the recording machine; copy it here if needed) fit
   `residual = slip_angle_rl_deg − k·steering_norm` per session and report:
   correlation of `residual` with `steering_norm` after the fit, its spread, and
   its value at Repsol apex on lap 15 vs a straight. Success criterion for the
   mechanism hypothesis: the fitted `k` removes the steering dependence
   (`|r| < 0.1`) but the residual stays large and unbounded — i.e. the recorded
   angle is a *direction*, not a slip. Write the numbers in `learnings.md`.
   Do not ship the spike.
2. **Decide the schema rows** (below) and write the refusal sentence, which must
   state the mechanism the spike proved, not a hedge.
3. **Rewrite `_SLIP_REASON`** and pin it in a test. This is the deliverable that
   answers acceptance criterion #1 for *this* session: the driver-facing report
   says why, in one verifiable sentence.

### B — recorder, on the recording machine

4. `Frame` + `writer._SCHEMA` gain, all nullable so every existing reader and
   every committed reference lap keep loading unchanged:
   `grip_fraction_rl`, `grip_fraction_rr`, `wheel_ground_vel_lat_rl/_rr`,
   `wheel_ground_vel_lon_rl/_rr`, `yaw_rate_radps`.
   Populate in the LMU reader and in the rF2 fallback reader (same
   `mWheels[i]` fields exist there).
5. **Record one calibration session** at Barcelona: a straight, then 2–3 laps
   with a deliberate rear slide on Repsol (brake held into the apex) and one
   clean lap.
6. **Validation gates** on that recording, before any product surface reads it:

   | case | expected |
   |---|---|
   | straight, constant speed | `grip_fraction_rl < 0.05`, rear slip angle ≈ 0° ± 1° |
   | hairpin, clean | rear slip 2–6°, `grip_fraction_rl` 0.1–0.4 |
   | Repsol, brake held, rear stepping | rear slip ≥ clean-lap value **and** `grip_fraction_rl` rises through the apex |
   | yaw-rate cross-check | sign of `atan2` slip matches sign of `yaw_rate` when the car is rotating |

   If the straight-line case does not sit near zero, the frame hypothesis is
   wrong: fall back to `atan2` with `mToe`, then to `mRotation`-based slip ratio,
   and if none is physically sane, stop and file the refusal as the outcome.

### C — analysis tail (any machine, needs a recording from B)

7. `CornerExtras` gains `rear_slip_apex_deg` (slip angle at the driver's apex)
   and `rear_grip_sliding_duty` (fraction of the corner with
   `grip_fraction_rl > 0.5`); both `None` when the columns are absent, so old
   sessions keep refusing.
8. Cite it in the corner drill-down (`session_conversation`) only. **No new
   priority/ranking term** in this slice — the prompt forbids it, and
   `trail_brake_depth_m` is the fact that used to carry this story.
9. Feature tests: register `rear-grip-signal` in `package.json`
   `testFeatures` with `test_runner_self_test.js`, `test_protocol_enforcement.js`,
   `test_python_interpreter.js`, `test_curated_utf8_names.js`, the new
   `test_rear_grip_signal.py` + its `.js` wrapper (TESTING_LESSONS L12),
   `test_session_corner_extras.js`, `test_bug_python_regressions.js`,
   `test_session_debrief_facts.js`. The new test pins: the refusal text on an old
   session, the numeric value on a small committed fixture recorded with the new
   columns, and `None` (not 0) for a session without them.
10. `npm run build` (no `dist/` change expected — this is Python only).

## Open questions to settle on the recording machine

- Does LMU zero-fill `mGripFract` (some builds report 0.0 always)? One straight +
  one slide answers it; if it is dead, the slice rests on the slip angle alone.
- Frame of the ground-velocity pair: the vendored header's comment is a
  copy-paste ("lateral velocity at contact patch" for both), so the gate in
  step 6 is the definition, not the comment.
- Sampling: the recorder polls at 50 Hz and the sim publishes at ~50–100 Hz; a
  slip angle is a derivative-like quantity, so check for aliasing on the slide
  traces before trusting the apex value.

## Cost / risk

Small code surface (one function, one schema list, both readers, five nullable
columns), one recording session, and a hard validation gate. The risk is that
`mGripFract` is unusable; the plan degrades to the slip angle only, and if that
also fails the slice ends with the sharpened refusal — which the prompt already
counts as a successful outcome.
