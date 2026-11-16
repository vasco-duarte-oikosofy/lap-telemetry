# Handoff — Slice 01 (true slip angle / verified refusal)

## State: ✅ closed. The number exists; the dead channel stays refused.

| Phase | What | State |
|---|---|---|
| A — spike + decision | mechanism proved, refusal rewritten, tests pin it | ✅ |
| B step 4 — schema + readers | 7 nullable columns in `Frame`, `writer._SCHEMA`, LMU + rF2 readers | ✅ |
| B steps 5–6 — calibration gates | answered from recordings already on disk (no new stint needed) | ✅ |
| C — analysis tail | `CornerExtras` rear-slip fact + drill-down citation | ✅ |

## The gates, answered

The blocker was "record a stint with a deliberate Repsol slide". That stint
already existed: the 2026-11-15 Barcelona sessions were recorded *after* phase
B4, so they carry the new columns. Measured on them
(`artifacts/channel-validation.txt`, reproduce with
`artifacts/validate_channels.py`):

| gate | expected | measured |
|---|---|---|
| straight, constant speed | slip ≈ 0 | median **0.03°** (Barcelona race), **0.04°** (Silverstone race) |
| lateral-acceleration response | grows with cornering, not with steering | **0.03°** < 0.3 g → **0.66°** 0.8–1.3 g → **1.46°** > 1.3 g |
| yaw cross-check | sign(slip) == sign(yaw) while rotating | **99.9%** of 58 199 rotating samples |
| Repsol, brake held | slip ≥ clean laps | **6.51°** vs 1.73–2.04° on the other 17 laps |

`mGripFract` **is dead in LMU**: `grip_fraction_rl` is a constant `0.0` in **all
61** recordings that carry the column. That is the answer to the plan's open
question, and it is a refusal, not a calibration problem.

## What changed on disk

| File | Change |
|---|---|
| `product/python/lap_telemetry/rear_slip.py` | **new** — the only producer of a rear slip number: `slip_series` (`atan2(lat, |lon|)` of the rear ground velocities), `column_reasons` (dead/absent channels with a reason), `measure_corner` (apex / braking-phase / peak slip + coverage), `attach_corners`, `assess_corner` / `assess_session` (three states), `describe` (the driver-facing sentence) |
| `product/python/lap_telemetry/session_corner_extras.py` | `CornerExtras` gains `rear_slip_apex_deg`, `rear_slip_braking_deg`, `rear_slip_peak_deg`, `rear_slip_coverage`; legacy `rear_slip_max_deg` / `_exit_deg` untouched |
| `product/python/lap_telemetry/session_facts.py` | attaches the rear-slip facts per lap and per reference; merges `column_reasons` into `unmeasurable_channels` |
| `product/python/lap_telemetry/session_brief.py` | the corner drill-down cites `rear stability: …` (three states) |
| `product/python/lap_telemetry/session_report.py` | human labels for the six new channel keys |
| `docs/ARCHITECTURE.md`, `recorder/writer.py` | the file format no longer claims `mGripFract` answers "was it sliding" |
| `dev/scripts/test_rear_slip_facts.py` + `.js` | **new**, 40 assertions, registered in `npm test` and `testFeatures.rear-grip-signal` |
| `artifacts/channel-validation.txt`, `artifacts/repsol-slide.txt`, `artifacts/validate_channels.py` | the evidence and its reproduction |

## The driver's account, answered with a number

> "At T4 (Repsol), the rear wants to come around at the apex if I keep the brake
> pressed."

On the 2026-11-15 18:44 Barcelona race, segment 6: **6.51°** rear slip at the
apex (`threshold 2.60°`, session baseline `1.73°`), and **4.87°** while the
brake was still applied — i.e. the slide overlaps the braking phase. Every other
lap of that race sits at 1.73–2.04°, so this is a single-lap event, not a
corner property. `assess_corner` marks it `measured_instability` with
`brake_overlap: true`.

The 2026-11-13 session that triggered the mission predates the columns and still
refuses, honestly (`unknown`, with the channel reason).

## Verified

- `bash scripts/test-summary.sh --feature rear-grip-signal`: **379 assertions /
  9 scripts — ALL PASS**.
- `bash scripts/test-summary.sh --feature session-debrief`: **813 assertions /
  25 scripts — ALL PASS** (the new facts change no existing number).
- `npm run build` unchanged (Python only).

## What slice 02 can now rely on

- `rear_slip.assess_corner(laps, corner_id, unmeasurable=…)` → `RearStability`
  with `state ∈ {measured_instability, no_detected_instability, unknown}`,
  `value_deg`, `baseline_deg`, `threshold_deg`, `braking_deg`, `brake_overlap`,
  `flagged[]` (segment, lap, clean, apex/braking values), `reason`.
- `rear_slip.assess_session(facts)` → the same for every corner.
- `rear_slip.describe(stability)` → one sentence with only numbers the facts
  carry, safe for the model validator.
- Reference laps are old parquets, so `reference_corners` carry **no** rear-slip
  values: a driver number is usable, a "vs reference" delta must never be
  invented.

## Deferred / open

- No `mToe` correction: the straight-line residual is 0.03°, i.e. smaller than
  the toe term it would correct. Do not add the column for it.
- `trail_brake_depth_m` (bug 36) is still not used to establish braking/sliding
  overlap — the overlap uses `brake_norm` directly.
- Grip fraction stays recorded (it costs seven floats) but no surface reads it.
