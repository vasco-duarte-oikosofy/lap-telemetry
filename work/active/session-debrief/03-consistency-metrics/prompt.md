# Slice 03: Consistency Metrics

## Goal

Answer the second half of the coaching question. Slice 02 says *where* time is
lost against the reference. This slice says **whether the driver is slow there
every lap or erratic there**, and how much of their own lap time is sitting in
their own inconsistency.

Those are different problems and need different coaching: "you are slow in
turn 3" versus "you get turn 3 right one lap in three".

## User-visible result

The `--json` payload gains a `consistency` section:

```json
"consistency": {
  "pace": {
    "clean_laps": 17, "best_lap_s": 79.135, "median_lap_s": 79.676,
    "worst_clean_lap_s": 82.491, "spread_s": 3.356, "std_dev_s": 0.850,
    "envelope_lap_s": 76.182, "time_available_s": 2.953,
    "basis": "speed_envelope"
  },
  "recurring_losses": [
    { "corner_id": "t3", "corner_name": "Sainte-Beaume", "phase": "minimum_speed",
      "mean_loss_s": 0.41, "laps": 17, "laps_affected": 15 } ],
  "inconsistent_corners": [
    { "corner_id": "t5", "corner_name": "Bretelle", "apex_s_m": 2180.0,
      "samples": 17, "mean_loss_s": 0.22, "best_loss_s": -0.05,
      "worst_loss_s": 0.61, "spread_s": 0.66 } ],
  "phase_spread": [
    { "corner_id": "t5", "corner_name": "Bretelle", "phase": "minimum_speed",
      "unit": "km/h", "samples": 17, "mean": 78.4, "best": 86.4, "worst": 71.0,
      "spread": 15.4, "std_dev": 4.1, "point_spread_m": 12.0 } ]
}
```

## Scope

### In scope

1. **Refactor first:** lift sector extraction out of `summary.py` into
   `lap_signals.sector_times()` so it is reusable and `summary.py` keeps its
   exact output. (Done as part of this slice; it is needed to *evaluate* the
   sector path, see below.)
2. `product/python/lap_telemetry/session_consistency.py`:
   - `speed_envelope_optimal()` — the theoretical best lap from the driver's own
     laps, by taking the fastest observed speed in each distance bin and
     integrating `Σ ds / v`. Sector-free.
   - `LapPace` — clean-lap spread: best, median, worst, spread, standard
     deviation, envelope lap, time available.
   - `PhaseSpread` — per corner-phase spread of the driver's own values
     (km/h for all three phases), plus the spread of the phase's distance.
   - `RecurringLoss` — mean loss per corner-phase across laps and how many laps
     it hurt: "slow every lap".
   - `CornerTime` — per corner, the spread in **seconds** of its delta-t loss
     across laps: "inconsistent here", unit-correct and comparable across
     corners.
   - `Consistency` — the container, with both rankings.
3. Wire into `SessionDebriefFacts` (`consistency` key) and `--json`.
4. Tests: `dev/scripts/test_session_consistency.py` (+ `.js`), added to the
   feature suite.

### Out of scope

- Extended channels: gear, brake area, trail-braking, slip, TC/ABS (slice 04).
- The ranked "what to change" list (slice 05) — this slice produces the two
  rankings it consumes.
- Sector-time optimal lap. See the decision below.

## Decision: no sector-based optimal lap

The PLAN said "optimal lap from best sectors (proxy when absent)". The data does
not support it:

| session | eligible laps | laps with usable sectors | boundary-updated |
|---|---|---|---|
| Paul Ricard 3A | 19 | 12 | 2 |
| COTA | 14 | 14 | 3 |

`last_sector_1_s` / `last_sector_2_s` are missing for whole laps and repeat
identical values across consecutive laps to the millisecond, so "sum of best
sectors" would be computed from a handful of laps and would be quietly wrong.
The **speed envelope** replaces it: it needs only `speed_kph` and
`lap_distance_m`, uses every clean lap, and is a standard "best of all laps"
metric. It is optimistic by construction (it assumes instantaneous speed
changes), which the report will say.

The sector extraction refactor still lands, because `summary.py` needs it and
because a future recorder fix will make the sector path possible.

## Design notes

- **Consistency uses clean laps only** (within 5% of the best eligible lap). A
  traffic lap inflates the spread and would send the driver chasing noise.
- **The envelope uses clean laps too**, and `time_available_s = best − envelope`.
  It is not a target for one lap; it is the size of the repeatability prize.
- **Two rankings, never merged.** `recurring_losses` is a mean, `inconsistent_
  corners` is a spread. A corner can top both, but the coach must be able to tell
  them apart.
- **Reuse `LapFacts.phases`.** No additional comparisons, no extra Node calls;
  the envelope needs two raw columns and nothing else.
- **Units are in the payload.** `PhaseSpread.unit` is `km/h`; `CornerTime` is
  seconds. Later slices must not have to guess.

## Steps

1. Write `prompt.md` (this file).
2. Refactor: `lap_signals.sector_times()` + `summary.py` uses it. Verify
   `summary` output is byte-identical. Commit `refactor:`.
3. Write `dev/scripts/test_session_consistency.py` first; watch it fail.
4. Implement `session_consistency.py`, wire into `session_facts.py`, `--json`.
5. `bash scripts/test-summary.sh --feature session-debrief` — green.
6. Verify by hand on the Paul Ricard fixture; check the two rankings name
   different corners.
7. Full suite (baseline 1553 passed / 4 pre-existing).
8. `handoff.md`, `learnings.md`, mark ✅ in `PLAN.md`, update the spec's
   optimal-lap line, commit, push.

## Acceptance

- `pace.best_lap_s` is the fastest clean lap; `spread_s` and `std_dev_s` match a
  hand computation; `envelope_lap_s < best_lap_s`; `time_available_s > 0`.
- The envelope of two synthetic laps (one faster in the first half, the other in
  the second) equals the harmonic sum of the per-bin best speeds.
- `inconsistent_corners` is ranked by seconds of spread, not km/h — a corner with
  a large km/h spread at low speed must not outrank a large time spread at speed.
- A corner that loses the same amount every lap appears in `recurring_losses`
  with a large mean and a small spread; an erratic corner appears in
  `inconsistent_corners` with a small mean and a large spread.
- Consistency uses only clean laps: a traffic lap must not change `best_lap_s`,
  `spread_s` or the envelope.
- `--json` remains one valid JSON document; `--list` is untouched.
