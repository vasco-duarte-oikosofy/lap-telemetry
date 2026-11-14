# Handoff — Slice 01 (true slip angle / verified refusal)

## State: half done, and the half that is done is green

The slice has three phases (`plan.md`). **A and B-step-4 are shipped; B steps
5–6 and all of phase C are blocked on one thing: a recording made *after* this
commit.**

| Phase | What | State |
|---|---|---|
| A — spike + decision | mechanism proved, refusal rewritten, tests pin it | ✅ shipped |
| B step 4 — schema + readers | 7 nullable columns in `Frame`, `writer._SCHEMA`, LMU + rF2 readers | ✅ shipped |
| B steps 5–6 — calibration recording + gates | needs a driving stint | ⛔ **blocked on the user** |
| C — analysis tail | `CornerExtras` rear-grip fact, drill-down citation | ⛔ not started (needs B5–6) |

Nothing in the product *reads* the new columns yet, by design. Existing sessions
keep refusing rear slip with the sharpened reason.

## What changed on disk

| File | Change |
|---|---|
| `product/python/lap_telemetry/session_corner_extras.py` | `_SLIP_REASON` rewritten with the measured mechanism; docstrings `unmeasurable_channels` / `_slip_is_usable` carry the numbers |
| `product/python/lap_telemetry/recorder/connect.py` | `Frame` gains `grip_fraction_rl/_rr`, `wheel_ground_vel_{lat,lon}_{rl,rr}`, `yaw_rate_radps`; new `_wheel_float()` and `_yaw_rate_radps()` helpers; both readers (LMU + rF2) populate them |
| `product/python/lap_telemetry/recorder/writer.py` | `_SCHEMA` + `append()` carry the 7 nullable columns |
| `docs/ARCHITECTURE.md` | file-format section: what the slip columns really are, and the new rear-grip columns |
| `dev/scripts/test_rear_grip_signal.py` + `.js` | 45 assertions (see below), registered as feature `rear-grip-signal` |
| `dev/scripts/test_session_corner_extras.py`, `dev/scripts/test_session_report.py` | the two assertions that pinned the *old* refusal wording (`"wrap"`) now pin the mechanism (`"atan2"` + `"steering"`) |
| `package.json` | `testFeatures.rear-grip-signal` (8 scripts) + the new test in `npm test` |
| `work/active/rear-grip-signal/01-true-slip-angle/artifacts/slip-spike.txt` | the throwaway spike's numbers (the script itself stays in git-ignored `var/tmp/slip_spike.py`) |

## The driver's account, answered honestly

> "At T4 (Repsol), the rear wants to come around at the apex if I keep the brake
> pressed."

**Not measurable in that recording** — and now the report says exactly why,
instead of a generic "values wrap":

> the sim value is atan2 of two contact-patch velocities in the car frame, so it
> idles at ±180° on a straight and follows steering input (r=+0.52); a tyre slip
> angle needs the wheel's own heading, and no wheel heading is recorded

That is a *successful* outcome for this slice per its own prompt: the answer is
a measurement, not a hedge, and the channel that would answer it is now
scheduled into the recorder.

## What the next session must be (the blocker)

Record one calibration stub **at Barcelona, in the Ginetta P3**, with this
commit's code running:

1. a straight at constant speed (~150+ km/h, 3 s),
2. 2–3 laps with a **deliberate rear slide on Repsol** — brake held into the
   apex, exactly the driver's sentence,
3. one clean lap.

Then the gates in `plan.md` phase B step 6:

| case | expected |
|---|---|
| straight | `grip_fraction_rl < 0.05`, rear slip ≈ 0° ± 1° |
| clean hairpin | rear slip 2–6°, `grip_fraction_rl` 0.1–0.4 |
| Repsol, brake held | rear slip ≥ the clean-lap value **and** `grip_fraction_rl` rising through the apex |
| yaw cross-check | sign of `atan2` slip matches sign of `yaw_rate_radps` while rotating |

If the straight-line case is not near zero, the frame hypothesis is wrong: fall
back to `atan2` with `mToe`, then to `mRotation`-based slip ratio, and if none is
physically sane, stop — the refusal is the outcome.

Two open questions the recording answers for free:
- Does LMU populate `mGripFract` at all (some builds report 0.0 always)?
- Which axis is yaw in `mLocalRot` (assumed `.y`)?

## Verified

- `bash scripts/test-summary.sh --feature rear-grip-signal`: **283 assertions /
  8 scripts — ALL PASS**.
- Full `bash scripts/test-summary.sh --pw`: **2847 assertions / 98 scripts —
  ALL PASS** (was 2800 / 97 before this slice).
- `npm run build` succeeded; `dist/compare.html` is byte-identical (Python-only
  change, reverted after the build check).
- New columns are nullable and every committed session/reference still loads —
  the full suite covers the loaders, the RLE path and the reference validator.
- Writing a `Frame` without the new fields produces **nulls, not 0.0**
  (asserted), and NaN readings are mapped to null rather than poisoning a
  column (asserted).
- **"Will it record?" is answered by test, not by hope:** the shipped test feeds
  the real `LMUConnection.read_frame()` a synthetic `LMUObjectOut` (the genuine
  ctypes image) with `mGripFract`, the rear ground velocities and `mLocalRot.y`
  set, and asserts the values survive SHM → `Frame` → parquet. The same test
  asserts the vendored LMU *and* rF2 ctypes mappings expose every field name the
  readers touch, so a vendored-header bump fails here instead of mid-session.
  The only thing left unproven is the sim itself (does LMU populate
  `mGripFract`, is `mLocalRot.y` the yaw axis) — that is gate one of the
  calibration stint.

## Deferred

- Phase C (the actual `rear_slip_apex_deg` / `rear_grip_sliding_duty` fact in
  `CornerExtras`, cited in the corner drill-down) — blocked on B5–6.
- Do not build on `trail_brake_depth_m` (bug 36 stays separate).
- The front wheels stay out of scope: they need a road-wheel angle whose gain is
  car-specific.
