# Bug 10: `lap_time_s` column underestimates lap time by 0–180 ms

## Observed

`extract_reference_lap.py` uses `max(lap_time_s)` per segment to compute lap duration.
For a lap the driver confirmed as **1:11.3xx** on-screen, the script reports **1:11.079**
(lap 23) or **1:11.242** (lap 24) — both short of the real time.

Session: `sessions/session_20260528T174221Z_bahrain-outer-circuit_lmu.parquet`

| Lap | `max(lap_time_s)` | offset-corrected | frames/50 Hz | driver HUD |
|-----|-------------------|------------------|--------------|------------|
| 23  | 1:11.079          | 1:11.238         | 1:11.140     |            |
| 24  | 1:11.242          | 1:11.380         | 1:11.340     | ~1:11.3xx  |

## Root cause

When `lap_number` increments, `lap_time_s` resets immediately to a **negative** value
(typically −0.000 to −0.180 s) rather than to 0. This negative value represents how
far past the scoring-module update the finish-line crossing already was when the SHM
was next polled. The last frame recorded under the old `lap_number` therefore reflects
a time *before* the true crossing, not at it.

```
last frame of lap N :  lap_time_s = 71.079   (short of crossing)
first frame of lap N+1: lap_time_s = -0.158  (already -0.158 s into new lap)
true finish time   :  71.079 + 0.158 = 71.237 s
```

A negative first `lap_time_s` in lap N+1 proves `max(lap_time_s)` for lap N is
short by at least that boundary offset. A zero or positive first value does **not**
prove `max(lap_time_s)` is accurate; the segment's own start offset and the
available scoring fields still need to be evaluated.

## Current plan

Do **not** implement the original negative-`first_next` fix yet. Research showed it is probably incomplete: positive `first_next` does not prove raw `max(lap_time_s)` is correct, because the segment itself can start with negative `lap_time_s`.

Proceed in steps:

1. **Slice 10b — persist authoritative scoring timing fields.**
   - See [`10b_prompt.md`](10b_prompt.md).
   - Add scoring lap timing fields to new recorder output so we can evaluate `mLastLapTime`, scoring `mLapStartET`, and related fields directly.
   - Keep existing `lap_time_s` for compatibility and trace alignment.
2. **Evaluate impact on the stack.**
   - Record or inspect a session with the new columns.
   - Compare completed lap durations from `scoring_last_lap_time_s` against current `max(lap_time_s)` and boundary heuristics.
   - Check where duration decisions are made in `extract_reference_lap.py`, `dist/compare.html`, and coaching fact generation.
3. **Decide next implementation slice.**
   - If `scoring_last_lap_time_s` is reliable, use it as authoritative completed-lap duration where available.
   - Preserve fallback behavior for old parquets.
   - Only then update reference extraction, compare UI labels/selection, and coaching summaries as needed.

Original candidate fix, now treated only as a fallback hypothesis:

```python
max_t      = max(lap_time_s[start:end])
first_next = lap_time_s[end] if end < len(lap_time_s) else 0.0
offset     = abs(first_next) if first_next < 0 else 0.0
duration   = max_t + offset
```

## Research results: capture/timing semantics

### 1. Are all channels duplicated, or only timing/scoring?

Existing parquet files show timing/scoring fields are coarse while many telemetry fields change row-to-row.

Example: `dev/sessions/session_20260510T093245Z_circuit-de-barcelona_lmu.parquet` has 28,493 rows.

| Column | Same as previous row | Interpretation |
|---|---:|---|
| `lap_time_s` | 90.7% | coarse/scoring cadence |
| `session_time_s` | 90.7% | coarse/scoring cadence |
| `lap_distance_m` | 90.7% | old recordings used raw scoring distance |
| `speed_kph` | 7.2% | high-rate telemetry changes nearly every row |
| `steering_norm` | 7.4% | high-rate telemetry changes nearly every row |
| `pos_x_m` | 7.2% | high-rate telemetry changes nearly every row |
| `pos_z_m` | 7.2% | high-rate telemetry changes nearly every row |

A newer `dev/sessions/lusail_merged.parquet` includes both raw and integrated distance:

| Column | Same as previous row | Interpretation |
|---|---:|---|
| `lap_time_s` | 91.7% | coarse/scoring cadence |
| `session_time_s` | 91.7% | coarse/scoring cadence |
| `raw_lap_distance_m` | 91.9% | coarse scoring distance |
| `lap_distance_m` | 17.9% | recorder-integrated distance changes at recorder/telemetry cadence |
| `speed_kph` | 19.1% | high-rate telemetry |
| `pos_x_m` | 19.5% | high-rate telemetry |

Conclusion: the recorder is not simply duplicating every row. LMU/rF2 expose high-rate telemetry, but timing/scoring fields update around 5 Hz.

### 2. Are telemetry and scoring separate buffers?

Yes.

Code path: `product/python/lap_telemetry/recorder/connect.py`.

- LMU reads one mapped object, but it has separate sections:
  - `self._mmap.data.scoring`
  - `self._mmap.data.telemetry`
- The vendored LMU mapping (`vendor/pyLMUSharedMemory/lmu_data.py`) defines separate structures:
  - `LMUScoringData`
  - `LMUTelemetryData`
  - update flags `SME_UPDATE_SCORING` and `SME_UPDATE_TELEMETRY`
- rF2 uses physically separate mmap files:
  - `MM_SCORING_FILE_NAME`
  - `MM_TELEMETRY_FILE_NAME`
  - `MM_EXTENDED_FILE_NAME`

Current lap timing is computed by mixing scoring and telemetry fields:

```python
lap_number=int(tele_v.mLapNumber),
lap_time_s=float(scor_info.mCurrentET - tele_v.mLapStartET),
```

Relevant alternative fields also exist in the LMU/rF2 scoring structs:

- `scor_v.mLapStartET`
- `scor_v.mTimeIntoLap`
- `scor_v.mLastLapTime`
- `scor_v.mEstimatedLapTime`

These should be investigated before choosing the final duration formula.

### Online/plugin research

The rF2 shared-memory plugin documentation states output refresh rates:

- Telemetry: 50 FPS
- Scoring: 5 FPS

This matches the parquet observations above. Known plugin clients include Crew Chief, SimHub, rFactor 2 Log Analyzer, Second Monitor, and others.

The plugin monitor / Crew-Chief-like timing sample uses scoring fields this way:

- completed lap duration: `vehicle.mLastLapTime`
- completed sectors: `mLastSector1`, `mLastSector2 - mLastSector1`, `mLastLapTime - mLastSector2`
- current lap display: `scoring.mScoringInfo.mCurrentET - vehicle.mLapStartET`

Important distinction: in that sample, `vehicle` is the scoring vehicle, not telemetry vehicle. Our recorder currently computes `lap_time_s` from scoring `mCurrentET` minus telemetry `mLapStartET`.

### 3. Do we store a local recorder timestamp per row?

No.

`Frame` has no local monotonic/UTC timestamp field, and `SessionWriter` schema does not include one. The recorder loop does use `time.monotonic()` for polling cadence and distance integration, but that timestamp is not persisted per row.

Sidecars store session-level UTC metadata and `sample_rate_hz`, not row-level capture time.

Implication: existing parquet files can prove scoring-field quantization and boundary offsets, but cannot reconstruct exact local capture times for each row. Future recordings should consider adding a row-level monotonic capture timestamp for diagnostics.

## Reproducer

See `reproducer.py` in this folder. Run from project root:

```powershell
python work/active/bugs/10-lap-time-s-undercount/reproducer.py
```

Prints the boundary analysis for every lap in the Bahrain Outer session, showing
`max(lap_time_s)`, the offset, and the corrected time.

## Affected files

- `dev/scripts/extract_reference_lap.py` — `main()` duration computation
- `dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md` — procedure docs

## Status

✅ Fixed

- Bug 10b (scoring columns): commit 
- Bug 10c (authoritative lap duration): commit 
