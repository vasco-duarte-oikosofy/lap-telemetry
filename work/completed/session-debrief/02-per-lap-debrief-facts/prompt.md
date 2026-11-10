# Slice 02: Per-Lap Debrief Facts

## Goal

Turn the session's eligible laps into one structured `SessionDebriefFacts`
record — every lap, every corner, every phase, **uncapped** — and print it as
JSON from `lap-telemetry debrief --json`.

This is the data every later slice reasons over. Nothing in it is prose and
nothing in it is a model's opinion.

## User-visible result

```text
$ lap-telemetry debrief sessions/session_20260524T141613Z_paul-ricard---3a_lmu.parquet --json
{
  "type": "session_debrief",
  "schema_version": "1",
  "session": {
    "stem": "session_20260524T141613Z_paul-ricard---3a_lmu",
    "track": "Paul Ricard - 3A",
    "vehicle_name": "DKR Engineering #4:ELMS25",
    "car_slug": "ginetta-lmp3",
    "total_segments": 25, "eligible_laps": 19, "clean_laps": 17,
    "yardstick_s": 80.044, "reference_lap_s": 77.166,
    "reference_file": "..._time_01.17.166.parquet",
    "track_model_file": "paul-ricard---3a_dkr-engineering-4-elms25.json"
  },
  "laps": [
    { "segment_index": 1, "lap_number": 1, "lap_time_s": 84.804, "delta_s": 7.638,
      "clean": false,
      "phases": [ { "corner_id": "t1", "corner_name": "...", "phase": "minimum_speed",
                    "loss_s": 0.34, "driver_value": 151.2, "reference_value": 164.3, ... } ] }
  ],
  "excluded": [ { "segment_index": 0, "lap_number": 0, "duration_s": 8896.314,
                  "status": "out-lap", "reason": "first segment of a stint" } ]
}
```

And the gate:

```text
$ lap-telemetry debrief dev/sessions/session_20260905T065812Z_lusail-...practice.parquet --json
lap-telemetry debrief: 4 eligible laps; a debrief needs at least 5.
  seg 0  lap 9   1:25.400  incomplete  lap ends at 1512 m
  ...
```

## Scope

### In scope

1. **One analysis core.** `compare_lap_tables(driver_table, reference_table, ...)`
   already exists (refactor committed) — the debrief calls it per lap segment.
   No second implementation of phase detection or delta-t.
2. `product/python/lap_telemetry/session_inputs.py` — resolve `(track, car)` from
   the sidecar to a reference lap and a coaching model, read the reference table
   **once**, and compute its authoritative duration once. Overrides for
   `--reference` / `--track-model` / `--track` / `--car`.
3. `product/python/lap_telemetry/session_facts.py` — `SessionDebriefFacts`,
   `LapFacts`, `ExcludedLap`, `SessionSummary`, and `build_session_facts`.
   Reuses `CornerLoss` and `corner_loss_to_dict`; no parallel fact types.
4. `debrief --json` in `debrief.py`/`cli.py`, including the five-lap gate.
5. Tests: `dev/scripts/test_session_debrief_facts.py` (+ `.js`), added to
   `testFeatures["session-debrief"]`.

### Out of scope

- Consistency, optimal lap, spreads (slice 03).
- Gear, brake area, trail-braking, slip, TC/ABS (slice 04).
- Priorities, suggestions (slice 05), report (06), LLM (07–08).
- No `--laps` filter, no output files: `--json` prints to stdout.

## Design notes

- **Lap identity is the segment.** `compare_laps(lap_number=...)` is not used:
  the two laps numbered `1` in the Paul Ricard fixture (segments 1 and 4) are
  different laps with different durations. The facts must carry
  `segment_index` and prove it.
- **Uncapped by construction.** The live coach returns the top 3 losses and 3
  gains; the debrief passes `top_n=None` and recombines losses and gains into
  one phase list sorted by apex distance, so a corner-by-corner walk is possible.
- **The reference is read once.** Nineteen laps must not re-read and re-duration
  19 times the same reference file.
- **A lap that cannot be compared is reported, not fatal.** If the comparison
  core rejects a lap the classifier accepted (e.g. the coaching model's
  `lap_length_m` disagrees with the session), the lap goes into `excluded` with
  the reason and the debrief continues.
- **The gate is hard.** Fewer than five eligible laps: exit 1, print the
  inventory lines for the rejected laps, no JSON.

## Steps

1. Write `prompt.md` (this file).
2. Write `dev/scripts/test_session_debrief_facts.py` first; watch it fail.
3. Implement `session_inputs.py`, `session_facts.py`, `debrief --json`.
4. `bash scripts/test-summary.sh --feature session-debrief` — green.
5. Verify on the Paul Ricard fixture by hand (19 laps, phase count, deltas) and
   on the Lusail fixture (gate refuses).
6. Full suite — the baseline is 1553 passed / 4 pre-existing failures.
7. `handoff.md`, `learnings.md`, mark ✅ in `PLAN.md`, commit, push.

## Acceptance

- `laps` has one entry per eligible lap, keyed by `segment_index`, and the two
  laps numbered `1` carry their own durations (84.804 and 82.491).
- Every lap's `delta_s` equals `lap_time_s - reference_lap_s`.
- `phases` is uncapped: a lap returns more than the six entries the live coach's
  `top_n=3` would keep.
- `excluded` lists every non-eligible segment with its status and reason.
- The reference parquet is read exactly once per run.
- A four-lap session exits 1 with the gate message and prints no JSON.
- `debrief --list` still works exactly as in slice 01.
