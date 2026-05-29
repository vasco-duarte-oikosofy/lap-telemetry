# Slice 10b: Persist authoritative scoring lap timing fields

## Context

Bug 10 started as a reference-lap extraction issue: `extract_reference_lap.py` uses `max(lap_time_s)` as lap duration, but existing parquets show this can undercount completed laps by roughly 0–180 ms at lap boundaries.

Initial hypothesis was to correct only when the next segment starts with negative `lap_time_s`. Further investigation showed that is incomplete: positive `first_next` does not prove raw `max(lap_time_s)` is authoritative, because the segment itself may have started with an offset.

## What we found

### Recorder/parquet cadence

Existing sessions show timing/scoring fields repeat at about the scoring cadence while telemetry fields change much more often.

Example: `dev/sessions/session_20260510T093245Z_circuit-de-barcelona_lmu.parquet`

- `lap_time_s`, `session_time_s`, old raw `lap_distance_m`: ~91% same as previous row
- `speed_kph`, steering, position: mostly change row-to-row

A newer `dev/sessions/lusail_merged.parquet` includes both raw and integrated distance:

- `raw_lap_distance_m`: scoring cadence
- `lap_distance_m`: recorder-integrated/high-rate cadence

Conclusion: the recorder is polling high-rate telemetry, but timing/scoring data updates at lower rate.

### Plugin docs / online research

The rF2 shared-memory plugin used by LMU/rF2 states output refresh rates:

- Telemetry: 50 FPS
- Scoring: 5 FPS

Known clients include Crew Chief, SimHub, rFactor 2 Log Analyzer, Second Monitor, etc.

The plugin monitor / Crew-Chief-like sample uses:

- `vehicle.mLastLapTime` for completed lap duration
- `vehicle.mLastSector1`, `vehicle.mLastSector2`, `vehicle.mLastLapTime` for completed sector times
- `scoring.mScoringInfo.mCurrentET - vehicle.mLapStartET` for current lap display

Important: in that sample, `vehicle` is the scoring vehicle, not telemetry vehicle.

### What our recorder currently uses

In `product/python/lap_telemetry/recorder/connect.py` current `Frame` fields are populated as:

```python
session_time_s = float(scor_info.mCurrentET)
lap_number     = int(tele_v.mLapNumber)
lap_time_s     = float(scor_info.mCurrentET - tele_v.mLapStartET)
```

This mixes scoring `mCurrentET` with telemetry `mLapStartET`, which may contribute to boundary inconsistencies.

Relevant scoring fields already available on `scor_v`:

- `mLapStartET`
- `mTimeIntoLap`
- `mLastLapTime`
- `mEstimatedLapTime`
- `mTotalLaps`

## Outcome

New recordings persist the scoring timing fields needed to evaluate and use authoritative completed-lap durations, without breaking existing parquet readers.

## Scope

This slice is an experiment / instrumentation slice. Do not yet rewrite the whole stack around a new duration model.

Implement the smallest useful changes:

1. Extend `Frame` with nullable diagnostic/official scoring fields:
   - `scoring_lap_start_et_s`
   - `scoring_last_lap_time_s`
   - `scoring_time_into_lap_s`
   - `scoring_total_laps`
   - optionally `telemetry_lap_start_et_s` for comparison
2. Populate these fields for both LMU and rF2 in `connect.py`.
3. Extend `SessionWriter` parquet schema and append logic with nullable columns.
4. Keep existing `lap_time_s` column for compatibility and trace alignment.
5. Add tests proving:
   - new schema columns exist and are nullable/backward-compatible
   - recorder/writer persists the new fields from a synthetic `Frame`
6. Update `bug.md` with results and any surprises.

## Non-goals

Do not yet:

- Change `dist/compare.html` lap selection or duration labels.
- Change coaching fact generation.
- Change reference-lap extraction duration logic.
- Rewrite existing parquets.
- Remove or rename `lap_time_s`.

Those decisions come after evaluating recordings with the new fields.

## Acceptance

- Tests fail before implementation and pass after.
- `bash scripts/test-summary.sh --feature <appropriate-feature-or-bug-suite>` or the closest targeted test command passes.
- `npm run build` succeeds if any web/dist-facing code changed; otherwise note why it was not required.
- `bug.md` records what was added and how to evaluate the next recording.
