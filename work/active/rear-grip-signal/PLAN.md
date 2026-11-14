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

**Feature tests:** `rear-grip-signal` is **not yet** registered in
`package.json` (`testFeatures`). Add it when slice 01 starts implementing, with
`dev/scripts/test_runner_self_test.js` + `dev/scripts/test_protocol_enforcement.js`
included, per `AGENTS.md`.

---

## Vertical slices

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-true-slip-angle` | 📝 Planned — see [`01-true-slip-angle/plan.md`](01-true-slip-angle/plan.md) | The existing `slip_angle_*` channel is either replaced by a verified real slip angle (new columns where needed, new fact where available) or the refusal is upgraded to a measured, specific reason. One session, one corner, one honest answer about whether the rear slid. |

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
