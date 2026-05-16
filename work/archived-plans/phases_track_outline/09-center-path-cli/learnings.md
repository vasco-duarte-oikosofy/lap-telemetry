# Learnings — Phase 09 Center/Path Polyline CLI

1. **Float32 Parquet round-trip affects x/z position values.** The same issue from Phase 08.1 affects pos_x_m and pos_z_m — values like `646.2` come back from Parquet as `646.1999816894531`. Tests that compare averaged position values must use `Math.abs(actual - expected) < epsilon` rather than strict equality when the fixture data is stored as float32 in Parquet.

2. **Path JSON uses `points` not `samples`.** This intentionally distinguishes the path output from the width profile output so downstream code can tell which dataset a file contains at a glance.

3. **Averaging is simpler than the width profile's max-accumulation.** For the center path, we average `pos_x_m` and `pos_z_m` within each bin. The `buildPathFromRows` pure function accumulates sums and counts, then divides at the end. This differs from `buildProfileFromRows` which takes the max per side.

4. **No gap-filling in this phase.** Unlike the width profile (which fills all bins between min and max s_m with explicit missing bins), the path simply omits bins with no data. This keeps the path data "raw" — interpolation/gap-filling will be handled in later boundary polyline phases that need to align path with width data.

5. **`readPathRows` reads pos_x_m and pos_z_m from Parquet.** The width profile's `readSessionRows` reads `path_lateral_m` and `track_edge_m`. Both read `raw_lap_distance_m` and `lap_number`. A later phase could share the `schemaNames` helper and Parquet reading infrastructure, but for now the duplication is intentional to keep each CLI self-contained.

6. **Real Spa endurance data: 5615 path points from 118419 input rows, 0 skipped.** All rows have valid position fields, which makes sense — position data is always present in LMU telemetry recordings.