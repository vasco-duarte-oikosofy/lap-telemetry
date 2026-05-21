# Handoff — Slice 01c: Determine Entry/Exit Phase Algorithm

## What is on disk now

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** — Main algorithm file. Contains:
  - `PhaseDetectionThresholds` dataclass with all configurable thresholds including `look_back_m`
  - `CornerLoss.phase_distance_m` — field for the actual distance where a phase was measured
  - `CornerLoss.driver_apex_distance_m` / `reference_apex_distance_m` — for `minimum_speed` phase
  - `find_entry_point(speed, throttle, brake, corner, thresholds, look_back_m=200)` — detects entry via throttle lift (preferred) or speed peak (fallback); searches 200m before `s_start_m` by default
  - `find_brake_point(brake, corner, thresholds, look_back_m=200)` — also uses look-back
  - `find_exit_points(brake, throttle, corner, thresholds)` — detects brake-off and/or full-throttle exit points
  - `compute_minimum_speed_per_corner()` — now returns 5 values: `(driver_min, ref_min, delta, driver_apex_m, ref_apex_m)`
  - `compare_laps()` — accepts optional `thresholds` param; loads throttle/brake; uses algorithm-driven entry/exit; populates apex offset fields

### New files
- **`dev/scripts/test_phase_detection.py`** — Unit tests (14 test functions, 55 assertions)

### Spec updates
- `docs/specs/interactive-race-coach-and-engineer.md` — Updated entry/exit detection (done); added apex offset open question with Imola reference

## Key algorithm detail: look-back

Throttle lift and braking for corners often start 50-100m before the formal `s_start_m` zone boundary. The `find_entry_point` and `find_brake_point` functions now accept `look_back_m` (default 200m) and search from `max(0, s_start_m - look_back_m)` toward the apex. This fixed a bug where Turn 6 at Barcelona produced a spurious "gain" because the throttle lift at 2438m was 64m before the zone starting at 2502m, causing the algorithm to fall back to `speed_peak` at the zone boundary (147 kph mid-corner instead of 204 kph entry speed).

## How to verify
```bash
cd product/python && python3 demo_coach_slice01.py --verbose
```
- Entry distances are detected at the actual throttle lift or speed peak, NOT at `s_start_m`
- Exit distances are detected at brake-off / full-throttle, NOT at `apex + 30`
- `minimum_speed` phases include `driver_apex_distance_m` and `reference_apex_distance_m`
- Barcelona turn 3: driver apexes 9m late (1170m vs 1161m reference)
- Barcelona turn 6 entry: now detected at throttle lift (~2439m), not zone boundary (2502m)

## Deferred TODOs
- Multi-apex corner support (test with Imola chicanes)
- Replace `loss_s = speed_delta / 100.0` with integrated time loss
- Entry distance comparison between driver and reference (both detected independently)
- Straight-zone time-loss analysis
- Reference lap brake/throttle phase detection for "you lifted later than reference" coaching
- Decide whether `apex_offset_m` should become a convenience computed field