# Learnings — Phase 02 Loader New Channels

- Browser loading already preserves requested Parquet columns as plain arrays; exposing the new read-only channels only required adding them to the load column list.
- Missing optional columns come through as empty arrays from `readColumns`, which fits the legacy-session contract and avoids synthesizing `raw_lap_distance_m` from `lap_distance_m`.
- Existing panel visibility remains data-driven: legacy fixtures without ABS/TC activity still render the established 8 telemetry panels.
