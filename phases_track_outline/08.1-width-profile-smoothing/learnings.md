# Learnings — Phase 08.1 Width Profile Smoothing

1. **Smoothing window bleeds into near-gap bins.** A window of 5 means bins within 5 positions of a gap include interpolated values in their average. Test fixtures need wide flat regions (10+ bins) to avoid this effect when testing "untouched" bins.

2. **Short datasets + large window = global average.** With only 5 bins total and window=5, the moving average just computes the mean of all bins. Test fixtures must be wide enough for the window to produce meaningful local averages.

3. **Extracting smoothing into its own module paid off.** `export_width_profile.js` was already at 214 lines. Adding ~100 lines of interpolation + smoothing logic would have pushed it well past the 200-line default. The separate `scripts/width_profile_smoothing.js` keeps each file focused.

4. **Two-pass design is clean: interpolate first, then smooth.** Interpolation fills gap bins with intermediate values. Smoothing then operates on the interpolated array, producing a consistent result. The intermediate `left_width_interpolated_m` field is internal-only and not exposed in output.

5. **`--smooth` flag defaults off preserves backward compatibility.** All existing tests and consumers get the same raw output. The new smoothed fields appear only when explicitly requested. This avoids breaking any downstream code.

6. **Long-gap barriers prevent smoothing artifacts.** Without barrier detection, the moving average would pull good bins toward zero across large missing sections. The barrier logic ensures long gaps act as walls.

7. **One-sided neighbor interpolation is conservative.** When a gap is at the start or end of the profile (only one non-missing neighbor), the smoother extends that neighbor's value rather than extrapolating. This avoids inventing data.

8. **CRITICAL: One-sided bins with zero width ≠ zero-width measurement.** Real LMU Spa data showed one-sided bins (e.g. left_sample_count=0, left_width_m=0) contaminating per-side moving averages. The smoother was treating `left_width_m=0` as a real zero-width measurement, dragging complete bins' smoothed values down by ~10m. Fix: compute per-side smoothing where each side only averages over bins that actually have data on that side. Check `has_left`/`has_right` flags (derived from sample counts), not just width values.

9. **Interpolation boundary neighbors must also respect has_left/has_right.** When interpolating a short gap's left side, only use the neighbor's left width if that neighbor actually has left data (`has_left=true`). Otherwise a one-sided neighboring bin with `left_width_m=0` gets treated as a valid anchor point for linear interpolation. Check the flag, not the width value.

10. **Per-side smoothing also correctly infers missing-side values.** 1138 one-sided bins with no left data got inferred left smooth values from nearby bins that DO have left data. This is the intended behavior: smoothing fills in gaps from neighbors.

11. **Float32 Parquet round-trip strikes again in real data.** Spa endurance left/right widths like 8.899999618530273 come from float32 precision limits. Smoothed values use full float64 arithmetic internally but the raw inputs carry float32 artifacts.