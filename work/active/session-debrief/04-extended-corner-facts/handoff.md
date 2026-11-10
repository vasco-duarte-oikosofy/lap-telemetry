# Handoff — Slice 04: extended corner facts

## State on disk

| File | Job |
|---|---|
| `product/python/lap_telemetry/session_corner_extras.py` | Channel extraction: gear, brakes, steering, flags, line, and the refusal rules |
| `product/python/lap_telemetry/session_facts.py` | `LapFacts.corners`, `SessionDebriefFacts.reference_corners`, `session.unmeasurable_channels` |

Payload sections now: `type, schema_version, session, laps[].corners,
consistency, reference_corners, excluded`. Paul Ricard JSON is 338 KB
(9 corners × 18 laps).

## What is measured

Per corner per lap: `gear_min`, `gear_at_apex`, `gear_at_exit`, `brake_peak`,
`brake_area` (pressure-metres), `trail_brake_depth_m`, `steering_reversals`,
`steering_rate_std`, `tc_duty`, `abs_duty`, `lateral_at_apex_m`,
`lateral_offset_m`, plus `window_source` (`phases` / `corner_model` /
`reference_phases`).

Windows come from the phases slice 02 already detected — entry → apex for
braking, the driver's own minimum-speed distance for the apex, first brake
release after the apex for trail depth.

## What is refused, and why

`session.unmeasurable_channels` is a `{channel: reason}` map, currently:

- `abs_active` — never active in the session (dead channel, or a car without
  ABS; we cannot tell which).
- `slip_angle_rl_deg`, `slip_angle_rr_deg` — the values wrap at ±180° and track
  neither turn rate nor braking. **Rear slip is not available from these
  recordings.** Do not reintroduce it without new evidence; the guard is
  `SLIP_SANE_MAX_DEG = 60`.

## Numbers that matter for slice 05

Reference (Paul Ricard 3A): t1 Bretelle 1st gear, brake 0.97, trail 10 m ·
t3 Signes 5th, brake 0.20 · t8 la Tour 2nd, brake 0.78, trail 81 m (still on
the brake at the corner's end) · t7 Village no braking, no trail.

Driver across 18 laps: Signes is taken in **both 5th and 6th** (a real
inconsistency to coach), t2 is 1st or 2nd, la Tour 1st or 2nd. Lateral offsets
range to 3.7 m off the reference at Beausset 1.

## Tests

`dev/scripts/test_session_corner_extras.py` (+ `.js`), 56 assertions, in the
feature suite: 629 assertions across 21 scripts. Full suite: **1666 passed**,
same 4 pre-existing failures.

## Deferred / traps

- Chained corners (Beausset 1 → 2) share one braking event; the second corner's
  `brake_peak` reflects residual pressure only. Do not over-read it.
- `tc_duty` on the *reference* is 0.0 for Paul Ricard but the reference's
  channel is sparse; the driver's session channel is dense, so the duty is
  honest for laps and should not be compared to the reference.
- `brake_area` units are normalised-pressure × metres; they are comparable
  across laps and drivers of the same session, not across tracks.
- Reference gear/brake facts are keyed by corner id, not by lap: join on
  `corner_id` in slice 05.
