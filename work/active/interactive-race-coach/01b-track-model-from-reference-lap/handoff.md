# Slice 01b Handoff: Track Model From Reference Lap

## Status

✅ Complete

## What's on disk now

- `dev/scripts/generate_track_coaching_model_from_reference.py`
  - CLI that reads a reference-lap Parquet file and emits a reviewable track coaching model.
  - Detects telemetry apex proxies from smoothed speed local minima.
  - Requires/reference-records a car identity via `--car-id`, vehicle/car columns, sidecar metadata, or reference-lap filename parsing.
  - Does not overwrite product track-coaching data.
- `dev/scripts/test_generate_track_coaching_model_from_reference.js`
  - Synthetic tests for one/two V-shaped corners, duplicate-minimum merging, and car identity failure/override.
  - Barcelona reference-lap smoke test asserts candidates near 829m, 941m, 1162m, and 1730m.
- `product/data/track-coaching/circuit-de-barcelona_dkr-engineering-4-elms25.json`
  - Reviewable car-specific generated model promoted into product data for demo/default smoke use.
- `product/python/demo_coach_slice01.py`
  - Defaults to the car-specific generated Barcelona model while still calling production `load_track_coaching_model()` and `compare_laps()`.
- `product/python/README.md`
  - Documents the demo maintenance rule so future coach fact/model changes keep the human smoke script and example output current.
- `package.json`
  - Full suite now includes the new generator test.
- `work/active/interactive-race-coach/PLAN.md`
  - Lists `01b-track-model-from-reference-lap` as complete.
- `work/active/interactive-race-coach/01b-track-model-from-reference-lap/artifacts/`
  - `circuit-de-barcelona.generated-track-coaching.json`
  - `circuit-de-barcelona.generated-track-coaching.diagnostics.txt`

## How to run

```bash
python3 dev/scripts/generate_track_coaching_model_from_reference.py \
  --reference-lap product/data/reference-laps/circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet \
  --track-id circuit-de-barcelona \
  --layout-id lmu-default \
  --car-id dkr-engineering-4-elms25 \
  --out work/active/interactive-race-coach/01b-track-model-from-reference-lap/artifacts/circuit-de-barcelona.generated-track-coaching.json \
  --diagnostics-out work/active/interactive-race-coach/01b-track-model-from-reference-lap/artifacts/circuit-de-barcelona.generated-track-coaching.diagnostics.txt
```

## Current Barcelona generated first-sector candidates

```text
t1 apex=841m start=808m end=890m
t2 apex=940m start=890m end=1050m
t3 apex=1161m start=1050m end=1280m
t4 apex=1731m start=1677m end=1850m
```

These match the visual review targets within the prompt tolerance.

## Algorithm defaults

- `smooth_window_m=5`
- `local_radius_m=8`
- `prominence_window_m=80`
- `min_prominence_kph=2.5`
- `min_separation_m=60`
- `zone_threshold_kph=1.0`
- `max_zone_half_width_m=120`

Apex side is not inferred. The generated JSON uses `--default-apex-side right` by default and marks each corner with `apex_side_source: default_cli_option` for review.

## Test results

- `bash scripts/test-summary.sh dev/scripts/test_generate_track_coaching_model_from_reference.js`: ✅ 21 assertions
- `bash scripts/test-summary.sh`: ✅ 1106 assertions across 47 scripts
- `npm run build`: ✅ rebuilt `product/dist/compare.html`

## Deferred TODOs

1. Derive or review `apex_side` instead of using the provisional default.
2. Replace or rename the older hand-authored Barcelona model only after explicit visual review.
3. Improve zone start/end estimation using brake/throttle/steering once the loss algorithm uses true delta-time.
4. Handle multi-apex and flat-out complexes with richer signals than speed minima alone.
