# Learnings — Phase 08 Width Profile Confidence

1. **`track_edge_m` is signed in LMU data.** Real LMU telemetry uses negative `track_edge_m` for left-side samples. The sign is redundant with `path_lateral_m`, so `Math.abs()` is needed when computing width values. Without this fix, `max(0, -7.4) = 0` silently drops all left-side widths from real data.

2. **Gap filling is simple but important.** Iterating from `min(s_m)` to `max(s_m)` in steps of `binSizeM` and inserting zero-count bins for missing positions ensures downstream consumers don't have to infer gaps. The count jumped from 5615 to 7094 bins for the Spa endurance session after gap filling — ~20% were gaps.

3. **Fixed confidence values work well for Phase 8.** Using `complete=1, low-sample=0.75, one-sided=0.5, missing=0` is the simplest documented rule. No consumer needs finer granularity yet. Phase 12 diagnostics may introduce more nuanced metrics.

4. **MIN_SAMPLES=3 is a reasonable threshold.** With 4+ telemetry samples per second and 1-meter bins, 3 samples means the car spent at least ~0.75s near that bin position. Lower counts could be noise from a single pass through a section.

5. **Float32 precision bites in Parquet round-trip tests.** Values like 7.4 stored as float32 in Parquet come back as 7.400000095367432. The pure-JS `buildProfileFromRows` tests use exact equality, but Parquet round-trip tests need `Math.abs(actual - expected) < 0.001`.

6. **Status-to-summary-key mapping.** The `classifyBin` function returns statuses like `'low-sample'` but the summary key is `low_sample_bins` (underscore, not hyphen). The mapping `status.replace('-', '_') + '_bins'` handles this consistently.