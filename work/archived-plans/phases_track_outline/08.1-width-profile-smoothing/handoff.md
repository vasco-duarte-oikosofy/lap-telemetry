# Handoff — Phase 08.1 Width Profile Smoothing

State on disk:

- `scripts/width_profile_smoothing.js`
  - New module exporting `interpolateAndSmooth(samples, opts)`.
  - Takes raw samples array (from `buildProfileFromRows`), returns new array with `left_width_smooth_m` and `right_width_smooth_m` added.
  - Constants: `MAX_INTERPOLATE_GAP = 10`, `SMOOTH_WINDOW = 5`.
  - Two-pass algorithm:
    1. **Interpolation:** Linear interpolation across consecutive missing bins ≤ MAX_INTERPOLATE_GAP. Interpolates from bounding non-missing neighbors using `(j - gapStart + 1) / (gapEnd - gapStart + 1)` fraction. Gaps > MAX_INTERPOLATE_GAP are skipped.
    2. **Smoothing:** Moving average over ±SMOOTH_WINDOW bins. Long-gap bins (missing with zero interpolated width) act as barriers — not included in averages, not smoothed across.
  - Options: `opts.maxInterpolateGap`, `opts.smoothWindow` override defaults.
  - Returns deep copies; original samples array is not mutated.

- `scripts/export_width_profile.js`
  - Now imports `interpolateAndSmooth` from `./width_profile_smoothing`.
  - `exportWidthProfile` gains `smooth` parameter (default `false`).
  - When `smooth: true`, adds `left_width_smooth_m` and `right_width_smooth_m` to each sample in the output.
  - CLI gains `--smooth` flag.
  - Exported `interpolateAndSmooth` from module.exports for test access.
  - No raw-output changes without `--smooth`.

- `scripts/test_width_profile_smoothing.js`
  - 45 assertions covering all Phase 08.1 acceptance criteria.
  - Tests: short gap interpolation, long gap rejection, raw data preservation, spike smoothing, no smoothing across long gaps, CLI --smooth flag, CLI raw output, interpolation correctness with wide flat regions, existing test compatibility, real-session smoke.

- `package.json`
  - Added `node scripts/test_width_profile_smoothing.js` to `npm test`.

Smoothing algorithm details:

| Parameter            | Default | Description                                    |
|----------------------|---------|------------------------------------------------|
| MAX_INTERPOLATE_GAP  | 10      | Max consecutive missing bins to interpolate     |
| SMOOTH_WINDOW        | 5       | Half-window for moving average (bins per side)  |

Short gaps (≤10 bins): linearly interpolated, then smoothed.
Long gaps (>10 bins): left as zero/missing, act as smoothing barriers.
Raw fields (left_width_m, right_width_m, sample counts, status, confidence) are never modified.

Feature flags live:

- No new feature flags. `--smooth` is a CLI switch, default off.

Verification:

- `npm test` passed (all prior + 45 new assertions).
- `npm run build` passed; `dist/compare.html` unchanged (no frontend changes).

Deferred:

- Center path polyline → Phase 09.
- Boundary polylines → Phase 09.1.
- Browser UI changes.
- Configurable window/gap size via CLI args.
- Smoothing diagnostics → Phase 12.