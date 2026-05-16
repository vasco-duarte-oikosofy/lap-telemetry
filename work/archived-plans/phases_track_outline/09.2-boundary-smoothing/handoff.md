# Handoff — Phase 09.2 Boundary Smoothing

State on disk:

- `scripts/compute_boundaries.js`
  - Exports new `smoothBoundary(boundaryPoints, window, binSize = 1)` helper.
  - `computeBoundaries({ ..., smoothBoundaryWindow })` defaults to `0`, preserving Phase 9.1 behavior when omitted.
  - Boundary smoothing applies after raw boundary derivation.
  - Smoothing uses local quadratic fits over `s_m` for `x_m` and `z_m` to reduce jitter while preserving straights/curves better than raw moving averages.
  - Zero-width points (`width_m === 0`) remain fixed and split smoothing segments.
  - `s_m` gaps greater than `binSize * 2` split smoothing segments.
  - CLI supports `--smooth-boundary <window>`; output JSON includes `smooth_boundary_window`.

- `scripts/test_boundary_smoothing.js`
  - New Phase 9.2 tests: straight-line preservation, synthetic jitter reduction, circular-arc radius preservation, zero-width barriers, `s_m` gap barriers, window identity, CLI round-trip, computeBoundaries integration, and Spa real-data smoke checks.

- `package.json`
  - Adds `node scripts/test_boundary_smoothing.js` to `npm test`.

- `data/circuit-de-spa-francorchamps-endurance/default/`
  - Local visual QA artifacts were regenerated:
    - `boundaries-raw.html.json` / `spa-view-raw.html` — raw baseline with smoothed widths only.
    - `boundaries.json` / `spa-view.html` — smoothed boundary output with `smooth_boundary_window: 5`.
  - These data files are currently untracked in this checkout and were not staged for commit.

- `specs/TRACK_OUTLINE_APEX_DISTANCE.md`
  - Documents two deferred Phase 9.2 visual-QA limitations:
    1. Curved-section oscillation remains too high at places like La Source.
    2. One side of the outline disappears/collapses in some curves due to one-sided/zero-width coverage.

Verification:

- `npm test` passes.
- `npm run build` passes and rewrote `dist/compare.html`.
- Visual QA was performed side-by-side in `profile_viewer.js`.
  - Smoothing is visibly better than raw.
  - User identified remaining quality issues above and directed that they be documented for a future improvement so later phases can proceed.

Deferred:

- Boundary-quality/envelope phase: derive stable local left/right width envelopes from robust maxima over short windows, reject outlier edge hits, interpolate missing sides, and then derive/render boundaries from that stable envelope.
- Rendering learned outlines in the browser compare app remains Phase 10.
- Low-confidence styling remains Phase 11.
- Diagnostics/calibration docs remain later phases.
