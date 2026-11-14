# Mission: Rear Grip Signal

**Goal:** Make it possible to say, with a number, whether the rear of the car was
actually sliding — in a named corner, on a named lap — instead of refusing the
`slip_angle_*` channels and leaving the driver's account untested.

**Why now.** The Barcelona P3 race debrief (2026-11-13) had to write:

> **rear slip angle (left)** — values wrap at ±180° and do not track turn rate or
> braking; not a slip angle as recorded

while the driver was saying "at T4 the rear wants to come around at the apex if I
keep the brake pressed". The coach could neither confirm nor deny it, and the
plan for the next stint rested on the driver's word alone. That is the one place
in the debrief where the tool goes quiet on the question that matters most.

**Spec:** none yet. This mission is specced by its slice prompts; if the work
grows past two slices, write `docs/specs/rear-grip-signal.md` first.

**Feature tests:** `bash scripts/test-summary.sh --feature rear-grip-signal`
(registered in `package.json` `testFeatures` at `8a1011d`, 8 scripts / 283
assertions, including the `test_runner_self_test.js` +
`test_protocol_enforcement.js` infrastructure guards).

---

## Vertical slices

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-true-slip-angle` | 🔧 In progress `8a1011d` — phases A + B4 shipped, B5–6 + C blocked on one calibration recording | The recorded slip channel is proved to be `atan2` of two car-frame patch velocities (follows steering r=+0.52, idles at ±180° on a straight, no yaw information), so `_SLIP_REASON` now states that measured mechanism; the recorder ships 7 nullable columns (`grip_fraction_rl/rr`, rear `wheel_ground_vel_{lat,lon}`, `yaw_rate_radps`) that a real slip angle and a sliding/not-sliding answer need. Next: a Barcelona stint with a deliberate Repsol slide, then the gates in `plan.md` B6, then phase C (the `CornerExtras` rear-grip fact) |

**Where it is developed:** on the recording machine. The planning spike (`plan.md`
phase A) can run anywhere, but the outcome is a recorder slice — the shippable
number needs `mGripFract` / ground-velocity columns that only a new recording can
carry, so the validation gates need a session recorded there. Do not start the
product-side work from a workstation that cannot record.

---

## References

- [`product/python/lap_telemetry/session_corner_extras.py`](../../product/python/lap_telemetry/session_corner_extras.py) — `_slip_deg`, `_SLIP_REASON`, `unmeasurable_channels`
- [`product/python/lap_telemetry/recorder/connect.py`](../../product/python/lap_telemetry/recorder/connect.py) — `_slip_deg()` and the `Frame` fields feeding it
- [`product/python/lap_telemetry/recorder/writer.py`](../../product/python/lap_telemetry/recorder/writer.py) — `_SCHEMA`
- [`work/completed/session-debrief/04-extended-corner-facts/`](../completed/session-debrief/04-extended-corner-facts/) — where the refusal was introduced, and why
- [`work/active/bugs/36-trail-depth-wrapped-distance/`](../bugs/36-trail-depth-wrapped-distance/bug.md) — open bug in the same module; do not build the new fact on `trail_brake_depth_m`
