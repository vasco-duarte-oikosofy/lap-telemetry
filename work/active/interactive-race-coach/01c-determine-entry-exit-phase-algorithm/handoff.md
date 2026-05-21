# Handoff — Slice 01c: Determine Entry/Exit Phase Algorithm

## What is on disk now

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** — Main algorithm file. Changes from 01c + 01c.2:
  - `PhaseDetectionThresholds` dataclass with configurable thresholds
  - `CornerLoss.apex_offset_m` — new field for minimum_speed phases
  - `compute_delta_time_trace()` — cumulative time delta at 1 m resolution
  - `find_straight_end_after_corner()` — end of straight = next corner entry or end of lap
  - `find_entry_point()`, `find_brake_point()`, `find_exit_points()` — algorithm-driven phase detection
  - `compare_laps()` — uses delta-time for minimum_speed and exit gains, heuristic for all losses and entry gains
  - `LapComparisonFacts.to_dict()` — includes `apex_offset_m` when present

### Key sub-slices

#### 01c.2 — Delta-time gains (implemented)
- Minimum-speed gains: `loss_s = delta_t[straight_end] - delta_t[apex]` (real seconds)
- Exit gains: `loss_s = delta_t[straight_end] - delta_t[exit_point]` (real seconds)
- `apex_offset_m` field on all minimum_speed phases
- Losses unchanged (still use `speed_delta / 100.0`)
- Entry gains still use heuristic

#### 01c.3 — Losses and gains algorithm review (future)
- Decide whether losses should also use delta-time
- Decide on entry gain algorithm (reference entry detection + distance delta)
- Address heuristic vs. real time mixing across phases

## Barcelona output

```
t3 minimum_speed loss: loss_s=0.106  (heuristic: 10.6/100) apex_offset_m=-9.0
t5 exit gain: loss_s=-0.065  (delta-time: 0.364 - 0.429 = -0.065s)
```

## How to verify
```bash
cd product/python && python3 demo_coach_slice01.py --verbose
python3 dev/scripts/test_phase_detection.py
bash scripts/test-summary.sh
npm run build
```