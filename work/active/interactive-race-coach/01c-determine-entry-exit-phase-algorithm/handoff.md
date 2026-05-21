# Handoff — Slice 01c: Determine Entry/Exit Phase Algorithm

## What is on disk now

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** — Main algorithm file. Contains:
  - `PhaseDetectionThresholds` dataclass with all configurable thresholds
  - `CornerLoss.phase_distance_m` — field for the actual distance where a phase was measured (None for `minimum_speed` at apex)
  - `CornerLoss.driver_apex_distance_m` / `CornerLoss.reference_apex_distance_m` — for `minimum_speed` phase: the lap-distance positions where driver and reference hit minimum speed
  - `find_entry_point()` — detects entry via throttle lift (preferred) or speed peak (fallback)
  - `find_brake_point()` — detects brake application point (secondary entry fact)
  - `find_exit_points()` — detects brake-off and/or full-throttle exit points, with merge logic
  - `compute_minimum_speed_per_corner()` — now returns 5 values: (driver_min, ref_min, delta, driver_apex_m, ref_apex_m)
  - `compare_laps()` — accepts optional `thresholds` param; loads throttle/brake channels when present; uses algorithm-driven entry/exit; populates apex offset fields on `minimum_speed`
  - Legacy `compute_corner_entry_loss()` and `compute_corner_exit_loss()` kept but no longer called

### New files
- **`dev/scripts/test_phase_detection.py`** — Unit tests for the phase detection algorithm (12 test functions, 56 assertions)

### Spec updates
- `docs/specs/interactive-race-coach-and-engineer.md` — Updated entry/exit detection section to reflect slice 01c completion; added apex offset open question with Imola test reference

### Schema changes
- `CornerLoss.phase_distance_m: float | None` — included in `to_dict()` when not None
- `CornerLoss.driver_apex_distance_m: float | None` — included in `to_dict()` for `minimum_speed` phase
- `CornerLoss.reference_apex_distance_m: float | None` — included in `to_dict()` for `minimum_speed` phase
- Phase names expanded: `"entry"`, `"minimum_speed"`, `"exit"`, `"exit_brake"`, `"exit_throttle"`

## Feature flags / configuration
- `PhaseDetectionThresholds` controls all detection thresholds with sensible defaults
- `compare_laps()` accepts `thresholds` parameter (defaults to `PhaseDetectionThresholds()` if None)

## New helpers worth knowing about
- `find_entry_point(speed, throttle, brake, corner, thresholds) → (distance_m, method)` — method is `"throttle_lift"`, `"speed_peak"`, or `"zone_start"`
- `find_exit_points(brake, throttle, corner, thresholds) → [(phase_name, distance_m), ...]` — returns 1 or 2 exit phases
- `find_brake_point(brake, corner, thresholds) → int | None` — brake application point
- `compute_minimum_speed_per_corner(driver_speed, ref_speed, corner) → (min, min, delta, driver_apex_m, ref_apex_m)`
- `_try_column(table, name) → list[float] | None` — safe column extractor for optional Parquet columns

## How to verify
```bash
cd product/python && python3 demo_coach_slice01.py --verbose
```
- Entry distances should NOT be exactly `apex - 30`
- Exit distances should NOT be exactly `apex + 30`
- Exit phases may appear as `exit_brake` + `exit_throttle` (when >3 m apart) or merged `exit`
- `minimum_speed` phases include `driver_apex_distance_m` and `reference_apex_distance_m`
- Barcelona turn 3: driver apexes 9m late (1170m vs 1161m reference)

## Deferred TODOs
- Multi-apex corner support (test with Imola chicanes)
- Replace `loss_s = speed_delta / 100.0` with integrated time loss
- Entry distance comparison between driver and reference (both detected independently)
- Straight-zone time-loss analysis
- Reference lap brake/throttle phase detection for "you lifted later than reference" coaching
- Decide whether `apex_offset_m` should become a convenience field (computed from the two distances)