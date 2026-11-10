# Slice 04: Extended corner facts

## Goal

The per-lap facts so far know only one thing about a corner: speed. That is
enough to say *where* time is lost, not *why*. A driver who is told "you lose
0.7 s at Signes" cannot act on it. A driver told "you are in 7th at the apex
where the reference is in 6th, you brake 12 m early, and you release the brake
9 m before the apex" can.

This slice adds the channels that explain the speed: gear, brakes, steering,
rear slip, electronics, and the line.

## User-visible result

Every lap fact gains a `corners` list, and the payload gains the reference's own
values so a suggestion can compare like with like:

```json
"corners": [
  { "corner_id": "t11", "corner_name": "Signes", "apex_distance_m": 3434.0,
    "gear_min": 6, "gear_at_apex": 6, "gear_at_exit": 7,
    "brake_peak": 0.0, "brake_area": 0.0, "trail_brake_depth_m": null,
    "steering_reversals": 1, "steering_rate_std": 0.004,
    "rear_slip_max_deg": 1.9, "rear_slip_exit_deg": 0.6,
    "tc_duty": 0.0, "abs_duty": 0.0,
    "lateral_at_apex_m": 2.4, "lateral_offset_m": 1.8 }
]
```

## Scope

### In scope

1. `product/python/lap_telemetry/session_corner_extras.py`:
   - `CornerChannels` — the raw columns of one lap, converted once, so fifteen
     corners do not each re-read the table.
   - `CornerExtras` — the per-corner values, every field optional.
   - `extract_corner_extras()` — windows derived from the corner model and the
     phase distances the comparison core already found, not from a second
     analysis.
   - `lateral_offset_m` against the reference at the driver's own apex.
2. `session_facts`: `LapFacts.corners` and `SessionDebriefFacts.reference_corners`.
3. Graceful degradation: a missing column yields `null` and is omitted from the
   JSON, never zero-filled. A channel that exists but is constant across the
   whole session (e.g. `tc_active` always false in the dry) is reported as
   `null` with a session-level note, because "0% TC" there means "not
   measurable", not "perfect traction".

### Out of scope

- Any ranking or suggestion. Slice 05 decides what the numbers mean.
- Any rendering. Slice 06.

## Definitions

| Fact | Window | Definition |
|---|---|---|
| `gear_min` | corner zone | lowest gear sampled between `s_start_m` and `s_end_m` |
| `gear_at_apex` | ±5 m of apex | gear nearest the driver's minimum-speed distance |
| `gear_at_exit` | ±5 m of exit | gear where the driver's exit phase was detected |
| `brake_peak` | corner zone | maximum `brake_norm` |
| `brake_area` | entry → apex | `Σ brake_norm × ds`, i.e. normalised pressure-metres |
| `trail_brake_depth_m` | apex → straight end | last distance past the apex with `brake_norm > 0.05`, minus apex; `0` when the brake is already released at the apex, `null` when there is no braking at all |
| `steering_reversals` | corner zone | sign changes of `Δsteering_norm` between consecutive samples, ignoring changes below 0.02 |
| `steering_rate_std` | corner zone | standard deviation of `Δsteering_norm` per metre |
| `rear_slip_max_deg` | corner zone | max of the two rear slip angles, absolute |
| `rear_slip_exit_deg` | ±5 m of exit | same, at the exit distance |
| `tc_duty` / `abs_duty` | corner zone | fraction of samples where the flag is true |
| `lateral_at_apex_m` | ±5 m of apex | `path_lateral_m` at the driver's apex |
| `lateral_offset_m` | — | driver's lateral at its apex minus the reference's lateral at the same distance; positive = driver is further out |

Windows come from what the comparison already computed: the entry phase
distance, the driver's minimum-speed distance, the exit phase distance, and the
straight-end distance. When a phase was not emitted (no speed delta above the
threshold), the window falls back to the corner model's own boundaries — the
fact is still useful, and the fallback is recorded per corner.

## Test plan

1. **Synthetic, exact.** A table with known gear/brake/steering/slip/flag/line
   values: every extracted number must equal the hand-computed one, including
   the trail-braking depth past the apex and the reversal count.
2. **Degradation.** Drop each column in turn; the corresponding field is `None`
   and the JSON omits it. No zero-filling.
3. **Windows.** A corner whose entry phase was not detected still produces
   `gear_min` over the model zone, with `window_source = "corner_model"`.
4. **Real session.** Paul Ricard: the hairpin (Beausset 2) must report 2nd gear
   at the apex, a brake peak near 1.0 and a positive trail-brake depth; Signes
   must report a top gear near 6–7 with little or no braking. Reference values
   extracted once and shared.
5. **Payload.** `debrief --json` contains `corners` for every lap and
   `reference_corners` once.

## Why this is worth a slice

Slice 05 cannot compute "one gear lower at the apex" or "release the brake 3 m
past the apex" without these numbers, and slice 07's conversation cannot answer
"why" without them. They also make the report credible to a driver, who will
immediately check whether the telemetry agrees with what the car felt like.
