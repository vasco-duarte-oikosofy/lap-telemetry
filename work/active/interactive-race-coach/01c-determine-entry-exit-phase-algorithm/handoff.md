# Handoff — Slice 01c: Determine Entry/Exit Phase Algorithm

## What is on disk now

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** — Main algorithm file. Contains:
  - `PhaseDetectionThresholds` dataclass with all configurable thresholds
  - `CornerLoss.phase_distance_m` — new optional field for the actual distance where a phase was measured (None for `minimum_speed` which is at the apex)
  - `find_entry_point()` — detects entry via throttle lift (preferred) or speed peak (fallback)
  - `find_brake_point()` — detects brake application point (secondary entry fact)
  - `find_exit_points()` — detects brake-off and/or full-throttle exit points, with merge logic
  - `compare_laps()` — now accepts optional `thresholds` param; loads `throttle_norm`/`brake_norm` columns when present; uses algorithm-driven entry/exit instead of fixed 30 m offsets
  - Legacy `compute_corner_entry_loss()` and `compute_corner_exit_loss()` kept for backward compatibility but no longer called by `compare_laps()`

### New files
- **`dev/scripts/test_phase_detection.py`** — Unit tests for the phase detection algorithm using synthetic telemetry (10 test functions, 43 assertions)

### Schema changes
- `CornerLoss.phase_distance_m: float | None` — included in `to_dict()` output when not None
- Phase names expanded: `"entry"`, `"minimum_speed"`, `"exit"`, `"exit_brake"`, `"exit_throttle"`

## Feature flags / configuration
- `PhaseDetectionThresholds` controls all detection thresholds with sensible defaults
- `compare_laps()` accepts `thresholds` parameter (defaults to `PhaseDetectionThresholds()` if None)

## New helpers worth knowing about
- `find_entry_point(speed, throttle, brake, corner, thresholds) → (distance_m, method)` — method is `"throttle_lift"`, `"speed_peak"`, or `"zone_start"`
- `find_exit_points(brake, throttle, corner, thresholds) → [(phase_name, distance_m), ...]` — returns 1 or 2 exit phases
- `find_brake_point(brake, corner, thresholds) → int | None` — brake application point
- `_try_column(table, name) → list[float] | None` — safe column extractor for optional Parquet columns

## How to verify
```bash
cd product/python && python3 demo_coach_slice01.py --verbose
```
- Entry distances should NOT be exactly `apex - 30`
- Exit distances should NOT be exactly `apex + 30`
- Exit phases may appear as `exit_brake` + `exit_throttle` (when >3 m apart) or merged `exit`

## Deferred TODOs
- Multi-apex corner support (current single-apex model may misidentify transitions for chicanas)
- Replace `loss_s = speed_delta / 100.0` with integrated time loss
- Entry distance comparison between driver and reference (both detected independently)
- Straight-zone time-loss analysis
- Reference lap brake/throttle phase detection for "you lifted later than reference" coaching