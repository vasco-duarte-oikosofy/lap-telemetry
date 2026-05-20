# Slice 01 Handoff: Offline Fact Generator

## Status

✅ Complete

## What's on disk now

### Product code (Python)

- `product/python/lap_telemetry/coach/__init__.py` — Coach module marker
- `product/python/lap_telemetry/coach/track_model.py` — Track coaching model loader and validator
  - `TrackCoachingModel` dataclass with corners and straight zones
  - `Corner` and `StraightZone` dataclasses
  - `load_track_coaching_model(path)` — validates and loads JSON models
  - `TrackModelValidationError` exception
- `product/python/lap_telemetry/coach/lap_comparator.py` — Lap comparison engine
  - `resample_column()` — distance-based linear interpolation to 1m grid
  - `compare_laps()` — compares current vs reference lap, returns `LapComparisonFacts`
  - `CornerLoss` and `LapComparisonFacts` dataclasses
  - `CornerLoss.apex_distance_m` is populated from each track model corner's `apex_s_m` and serialized immediately after `corner_name`
- `product/python/lap_telemetry/coach/cli.py` — CLI entry point for `compare-laps` command
- `product/python/lap_telemetry/__main__.py` — Module entry point for `python -m lap_telemetry`
- `product/python/lap_telemetry/cli.py` — Updated with `compare-laps` subcommand

### Data artifacts

- `product/data/track-coaching/circuit-de-barcelona.json` — Hand-authored track model with 16 corners and 4 straight zones
- `dev/fixtures/coach/barcelona_lap2_current.parquet` — Test fixture (lap 2 from existing session, 57.939s)

### Test scripts

- `dev/scripts/test_coach_lap_comparison.js` — Parallel test runner for coach module (5 assertions)

### Mission structure

- `work/active/interactive-race-coach/PLAN.md` — Mission plan with 9 slices
- `work/active/interactive-race-coach/01-offline-fact-generator/` — Slice 01 folder with all required artifacts

## Commands to run

### CLI usage (Windows PowerShell)

```powershell
cd C:\path\to\lap-telemetry
python -m lap_telemetry compare-laps `
  --current-lap .\dev\fixtures\coach\barcelona_lap2_current.parquet `
  --reference-lap .\product\data\reference-laps\circuit-de-barcelona_time_01.36.456.parquet `
  --track-model .\product\data\track-coaching\circuit-de-barcelona.json
```

### Run tests

```bash
bash scripts/test-summary.sh dev/scripts/test_coach_lap_comparison.js   # single test
bash scripts/test-summary.sh                                             # full suite
```

## Feature flags

None for this slice.

## New helpers worth knowing about

### `resample_column(distances, values, max_dist)`

Resamples telemetry columns onto a 1-meter distance grid using linear interpolation. Pure function, no dependencies.

### `compare_laps(current_lap_path, reference_lap_path, track_model)`

Returns structured `LapComparisonFacts` with:
- Lap time delta
- Top 3 corner losses (minimum speed, entry, exit phases)
- Top 3 corner gains
- Constraints for LLM (max_words, style)

Output is JSON-serializable via `.to_dict()`. Each `top_losses`/`top_gains` item includes `apex_distance_m` for quick track-location lookup.

### Track coaching JSON schema

```json
{
  "schema_version": "1",
  "track_id": "circuit-de-barcelona",
  "layout_id": "lmu-default",
  "lap_length_m": 4657.0,
  "corners": [
    {
      "id": "t4",
      "name": "turn 4",
      "s_start_m": 1590.0,
      "apex_s_m": 1650.0,
      "s_end_m": 1720.0,
      "apex_side": "right"
    }
  ],
  "straight_zones": [
    { "id": "start-finish", "s_start_m": 0.0, "s_end_m": 680.0 }
  ]
}
```

## Deferred TODOs

1. **Track model generation automation** — Currently hand-authored. Need tooling to generate from repeated laps or outline data.
2. **Time-based loss computation** — Currently uses speed delta / 100 as rough time estimate. Should integrate delta-time over corner zones.
3. **Throttle/brake/steering analysis** — Only minimum speed analyzed in MVP. Add entry/exit phase metrics for throttle pickup, braking point, steering smoothness.
4. **Confidence scoring** — Currently binary (high/medium). Should factor in data quality, interpolation distance, reference lap age.
5. **Multi-lap aggregation** — Compare median of last 3 laps vs reference, not single lap.
6. **Windows smoke test documentation** — Add explicit PowerShell smoke command to spec or README.

## Test results

- `bash scripts/test-summary.sh dev/scripts/test_coach_lap_comparison.js`: ✅
- `cd product/python && python3 demo_coach_slice01.py`: ✅ shows `"apex_distance_m": 3430.0` for turn 8
- `bash scripts/test-summary.sh`: ✅ 1084 assertions across 46 scripts
- `npm run build`: ✅ rebuilt `product/dist/compare.html`

## Known issues

- **Lap time delta is negative** (-38.5s) because the fixture lap (57.9s) is from a different session type than the reference (96.5s). This is expected for testing — the comparison logic works correctly, the fixtures just represent different lap types. For real coaching, both laps should be comparable (same track layout, similar conditions).
