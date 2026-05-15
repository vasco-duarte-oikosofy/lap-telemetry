# Learnings — Phase 08.1 Width Profile Smoothing

1. **Smoothing window bleeds into near-gap bins.** A window of 5 means bins within 5 positions of a gap include interpolated values in their average. Test fixtures need wide flat regions (10+ bins) to avoid this effect when testing "untouched" bins.

2. **Short datasets + large window = global average.** With only 5 bins total and window=5, the moving average just computes the mean of all bins. Test fixtures must be wide enough for the window to produce meaningful local averages.

3. **Extacting smoothing into its own module paid off.** `export_width_profile.js` was already at 214 lines. Adding ~100 lines of interpolation + smoothing logic would have pushed it well past the 200-line default. The separate `scripts/width_profile_smoothing.js` at 106 lines keeps each file focused.

4. **Two-pass design is clean: interpolate first, then smooth.** Interpolation fills gap bins with intermediate values. Smoothing then operates on the interpolated array, producing a consistent result. The intermediate `left_width_interpolated_m` field is internal-only and not exposed in output.

5. **`--smooth` flag defaults off preserves backward compatibility.** All existing tests and consumers get the same raw output. The new smoothed fields appear only when explicitly requested. This avoids breaking any downstream code.

6. **Long-gap barriers prevent smoothing artifacts.** Without barrier detection, the moving average would pull good bins toward zero across large missing sections. The `isBarrier` array in the smoother ensures long gaps act as walls.

7. **One-sided neighbor interpolation is conservative.** When a gap is at the start or end of the profile (only one non-missing neighbor), the smoother extends that neighbor's value rather than extrapolating. This avoids inventing data.