# Handoff — Bug 28 (lap duration telemetry clock)

## What changed

- **Shared helper** `authoritative_duration` (Python) and `authDuration` (JS)
  now prefer the telemetry lap-start ET difference between consecutive laps
  (TinyPedal method) over the scorer's `mLastLapTime`.
- **Reference files** carry `authoritative_lap_time_s` in parquet schema
  metadata (written by `export_fastest_reference_laps.py`), so single-segment
  consumers get the exact value.
- **Road Atlanta** reference re-exported: `_time_01.17.345` →
  `_time_01.16.809`; coaching model `reference_lap` path + `lap_time_s`
  (77.345 → 76.809) updated.
- **Web**: `pipeline.js` `annotateSegments` accepts `sessionTimes`; `ui.js`
  loads `session_time_s` and passes it.
- **Tools**: `validate_reference_laps.py` provenance loads `session_time_s`;
  `extract_reference_lap.py::_authoritative_duration` delegates to the shared
  helper.

## Key facts to remember

- Recover the telemetry lap-start ET as `session_time_s - lap_time_s`.
- True lap duration = difference of that value between consecutive segments.
- `mLastLapTime` (`scoring_last_lap_time_s`) can lag a lap; do not trust it.
- `max(lap_time_s)` undercounts by the last partial sample (~0.09 s).
- Road Atlanta lap 15 = **1:16.809**; TinyPedal deltabest = 76.80896.
- Paul Ricard 1A-V2-Short quali lap 4 = 1:36.804 (scorer happened to agree
  there, so bug 13's tests still pass via the fallback).

## Deferred / open

- `test_bug13_authoritative_duration.js` still encodes the old scorer-first
  expectation for tables without `session_time_s`; its synthetic fixtures now
  exercise the legacy fallback only. A follow-up could rewrite it around the
  telemetry clock, but the new `test_lap_duration_telemetry` covers the
  ground truth.
- Bug 26 (track outline not visible) root cause was the `_lmu_<type>` filename
  regex, fixed in `c396279`/`b903909`; that bug folder still needs closing
  after user live confirmation.

## Commands

```bash
python dev/scripts/validate_reference_laps.py
PYTHONIOENCODING=utf-8 python -m lap_telemetry.cli summary \
  sessions/session_20261004T133118Z_michelin-raceway-road-atlanta_lmu_practice.parquet
node dev/scripts/test_reference_lap_duration.js
python3 dev/scripts/test_lap_duration_telemetry.py
npm run build
```
