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
(grown at slice 02 to 14 scripts / 582 assertions: the five shared debrief suites
— consistency, priorities, brief, report, conversation — joined the mission's own
`test_rear_grip_signal.js` and `test_rear_slip_facts.js`, together with the
`test_runner_self_test.js` + `test_protocol_enforcement.js` infrastructure
guards).

---

## Vertical slices

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-true-slip-angle` | ✅ Closed — phases A, B, C shipped | The recorded slip channel is proved to be `atan2` of two car-frame patch velocities (follows steering r=+0.52, idles at ±180° on a straight, no yaw information). The calibration gates were answered from recordings already on disk: rear slip from the wheels' ground velocities is **0.03° on a straight**, rises with lateral acceleration (0.03 → 0.66 → 1.46°), matches the yaw-rate sign on **99.9%** of rotating samples, and flags one real single-lap slide (Repsol **6.51°** against a 1.73° baseline, brake still on). `mGripFract` is **dead in LMU** — constant 0.0 in all 61 recordings that carry it — so it is refused, never read as "no slip". `CornerExtras` carries the rear-slip fact and the corner drill-down cites it |
| [`02-rear-slip-aware-debrief`](02-rear-slip-aware-debrief/prompt.md) | ✅ Implemented `c4a1fe3` | Advice, grounding, no-LLM answers, report and plan are rear-slip aware in three states (measured instability / nothing detected / unknown) without changing rank, recurring loss or pace. On the trigger session (Silverstone P3, 2026-11-14 19:04) Becketts measured **13.78°** apex slip with **5.61°** while braking, so "hold the brake 20 m longer" is replaced by a settle-first instruction and a stability target; on the Barcelona race the Repsol slide ranks #4 and still reaches the plan via an `Also measured:` line. One `RearStability` object feeds every surface, so they cannot disagree. Shared debrief suites added to the feature list: 14 scripts / 582 assertions; full `--pw` 3165 / 103 |

**Where it is developed:** the recorder columns shipped in phase B4, so the
remaining work happened on this workstation against sessions already on disk.
A new driving stint is only needed to re-validate a future channel change.

---

## References

- [`product/python/lap_telemetry/session_corner_extras.py`](../../product/python/lap_telemetry/session_corner_extras.py) — `_slip_deg`, `_SLIP_REASON`, `unmeasurable_channels`
- [`product/python/lap_telemetry/recorder/connect.py`](../../product/python/lap_telemetry/recorder/connect.py) — `_slip_deg()` and the `Frame` fields feeding it
- [`product/python/lap_telemetry/recorder/writer.py`](../../product/python/lap_telemetry/recorder/writer.py) — `_SCHEMA`
- [`work/completed/session-debrief/04-extended-corner-facts/`](../completed/session-debrief/04-extended-corner-facts/) — where the refusal was introduced, and why
- [`work/active/bugs/36-trail-depth-wrapped-distance/`](../bugs/36-trail-depth-wrapped-distance/bug.md) — open bug in the same module; do not build the new fact on `trail_brake_depth_m`
