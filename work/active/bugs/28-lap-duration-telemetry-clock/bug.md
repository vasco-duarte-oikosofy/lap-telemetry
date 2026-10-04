# Bug 28 — Lap duration must come from the telemetry lap-start clock, not the scorer

## Symptom

The same lap shows the wrong duration through the whole toolchain:

- `lap-telemetry summary` reported lap 15 of the Road Atlanta practice as
  **1:17.345**
- the reference lap file was named `..._time_01.17.345.parquet`
- the coaching model recorded `reference_lap.lap_time_s = 77.345`
- the in-game best lap for the same car/lap is **1:16.809**

TinyPedal's own recorded delta-best for `Michelin Raceway Road Atlanta - LMP3`
ends at **76.80896 s**, confirming 1:16.809.

## Root cause

`authoritative_duration` (Python) and `authDuration` (JS) preferred the sim
scorer's `mLastLapTime` (`scoring_last_lap_time_s`). On Road Atlanta that value
**lags by one lap**: during lap 16 the scorer still held lap 14's time
(`77.345`), so the helper returned 77.345 for lap 15 instead of 76.809.
`max(lap_time_s)` is closer but undercounts the last partial sample by ~0.09 s.

Bug 13/21 had established the scorer value as authoritative, but that was
based on sessions (Paul Ricard) where `mLastLapTime` happened to agree. It is
not reliable across tracks/session types.

## How TinyPedal does it (the reference implementation)

`../tinypedal/tinypedal/module/module_delta.py`:

```python
lap_stime = api.read.timing.start()          # lmuTeleVeh.mLapStartET (TELEMETRY)
...
if lap_stime > last_lap_stime:
    laptime_last = lap_stime - last_lap_stime   # consecutive lap-start ET diff
```

It derives the lap duration from consecutive **telemetry** lap-start ETs
(`lmuTeleVeh.mLapStartET`), not from the scorer. `module_stats.py` validates
`mLastLapTime` against that raw value and rejects mismatches.

Our recorder stores `lap_time_s = scor_info.mCurrentET - tele_v.mLapStartET`
and `session_time_s = scor_info.mCurrentET`, so:

```
session_time_s - lap_time_s == tele_v.mLapStartET   (constant within a lap)
```

The telemetry lap-start difference is therefore recoverable from existing
parquet files with no schema change.

## Fix

- `product/python/lap_telemetry/parquet_utils.py` — `authoritative_duration`
  now prefers, in order: (1) explicit `authoritative_lap_time_s` schema
  metadata, (2) telemetry lap-start ET difference to the next segment,
  (3) legacy `scoring_last_lap_time_s`, (4) `max(lap_time_s)`.
- `product/web/js/pipeline.js` — `authDuration` mirrors the same priority;
  `annotateSegments` takes `sessionTimes`; `ui.js` loads `session_time_s`.
- `dev/scripts/export_fastest_reference_laps.py` — writes the exact
  authoritative duration into the reference parquet schema metadata.
- `dev/scripts/validate_reference_laps.py` — provenance probe loads
  `session_time_s` so it can match the filename via the telemetry clock.
- `dev/scripts/extract_reference_lap.py` — `_authoritative_duration` delegates
  to the shared helper, and the manual extract path now stamps the exact
  duration into the output file's schema metadata too (mirroring the exporter).
- Road Atlanta reference re-exported to `_time_01.16.304`; coaching model
  path/time updated (the true fastest race lap).

## Verification

- `dev/scripts/test_lap_duration_telemetry.py`
  (`.../test_lap_duration_telemetry.js`): synthetic stale-scorer case,
  Road Atlanta lap 15 = 76.809, Paul Ricard lap 4 = 96.804, metadata override.
- `dev/scripts/test_lap_duration_surfaces.py` (`.../test_lap_duration_surfaces.js`)
  — every product surface: the recorder output contract
  (`session_time_s - lap_time_s` constant within each completed lap),
  `summary.run()` (race lap 15 = 1:16.304), `find_complete_laps()` selection and
  rejection of the restart-truncated 1:15.994 lap, `compare_laps()` coach delta
  (+0.113 s for lap 21), the extracted reference metadata/filename, and the
  manual-extract metadata stamp.
- `dev/scripts/test_compare_reference_duration.js` (Playwright) — loads the
  built `product/dist/compare.html` and asserts the session and reference
  pickers show 1:16.304 (run with `--pw`).
- `dev/scripts/test_reference_lap_duration.js`: JS telemetry priority +
  reference-filename override.
- `dev/scripts/test_bug13_authoritative_duration.js` still passes (its
  synthetic tables lack `session_time_s`, so the legacy scoring fallback runs).
- `lap-telemetry summary` now prints `1:16.304` for the race lap 15; the app
  session and reference pickers show `1:16.304 ★`.
- `validate_reference_laps.py`: 26 refs, 0 failures, provenance traced to the
  source session.
- Full suite (with `--pw`): 1260 passed, 6 pre-existing Windows ESM harness
  failures (unrelated).

## Status

🛠 Fixed and verified across all product surfaces — pending user live
confirmation before moving to `work/completed/bugs/`.
