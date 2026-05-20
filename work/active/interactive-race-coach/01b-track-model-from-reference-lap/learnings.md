# Slice 01b Learnings: Track Model From Reference Lap

## Surprises

1. **The Barcelona reference lap has a shallow second-sector-one minimum.** Around 940m the local speed dip is only about 3.4 km/h prominent, so a high prominence threshold misses it. The default threshold is intentionally low (`2.5 km/h`) to keep this review candidate.

2. **User-observed t1 at 829m maps close to reference-lap speed minimum at 841m.** The detector uses the reference lap, not the current comparison lap. The prompt's ±20m tolerance covers this difference.

3. **Reference Parquet files do not currently include a car identity column.** The generator supports explicit `--car-id` and filename parsing like `track_car_time_...parquet`. Synthetic tests cover the failure path when identity is truly absent.

4. **Apex side is not safely derivable from speed alone.** The generated model remains loader-compatible by using a default side, but it records `apex_side_source: default_cli_option` so reviewers know it is provisional.

## Context for the next agent

- The generated Barcelona artifact is intentionally under the slice `artifacts/` folder, not `product/data/track-coaching/`.
- First-sector generated apexes are:
  - t1: 841m
  - t2: 940m
  - t3: 1161m
  - t4: 1731m
- The script emits 11 Barcelona candidates with current defaults. It does not try to split every named Barcelona corner; it produces speed-minimum coaching zones.
- `load_track_coaching_model()` ignores extra fields, so `reference_lap` and `apex_side_source` do not break compatibility.

## Limitations

1. Speed minima are telemetry apex proxies, not geometric apexes.
2. Multi-apex turns and flat-out bends may need steering, throttle, brake, and track-outline cues.
3. Zone start/end estimation is intentionally simple and review-oriented.
4. Car-specific metadata is now recorded, but downstream code does not yet enforce car/model matching.
