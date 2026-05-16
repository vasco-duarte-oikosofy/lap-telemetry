# Handoff — Phase 09.1 Boundary Polylines

State on disk:

- `scripts/compute_boundaries.js`
  - New CLI script deriving left/right boundary polylines from path JSON + width profile JSON.
  - Exports `computeBoundaries({ pathPoints, profileSamples, useSmooth })` — pure function returning `{ left, right, use_smooth, summary }`.
  - Exports `computeTangentNormal(points, index)` — pure function returning `{ tx, tz, nx, nz }`.
  - Exports `computeBoundariesFromFiles({ pathPath, profilePath, outPath, useSmooth, overwrite })` — async file-based wrapper.
  - CLI: `node scripts/compute_boundaries.js --path <path.json> --profile <profile.json> --out <boundaries.json> [--smooth] [--overwrite]`
  - Normal: left normal = (-tz, tx) when tangent = (tx, tz). Left boundary = path + normal × leftWidth. Right boundary = path - normal × rightWidth.
  - Interior tangent: normalized vector from previous point to next point. Endpoints: one-sided to neighbor. Single/coincident points: zero tangent/normal.
  - Boundary points only where path and profile share same s_m. Unmatched path points counted but produce no boundary points.
  - Status/confidence propagated from width samples to boundary points.
  - Overwrite protection: refuses unless `--overwrite`.
  - Output JSON shape: `{ track_id, layout_id, bin_size_m, use_smooth, left: [{s_m, x_m, z_m, width_m, status, confidence}], right: [...], summary: { path_points, profile_samples, matched_bins, unmatched_path, left_boundary_points, right_boundary_points } }`

- `scripts/test_compute_boundaries.js`
  - 100 assertions covering Phase 9.1 acceptance criteria.
  - Tests: straight-line exact offsets, tangent/normal math, +x direction normals, circular arc side consistency, missing bins, status/confidence propagation, smooth vs raw widths, summary fields, single-point path, colinear points, CLI invocation, CLI --smooth, overwrite refusal, width field output, existing commands unchanged.

- `scripts/profile_viewer.js`
  - Now accepts `--boundaries <boundaries.json>` flag.
  - Renders left boundary in red (#e63946) and right boundary in teal (#2a9d8f) on the 2D track map.
  - Legend and info line updated with boundary counts.

- `package.json`
  - Added `node scripts/test_compute_boundaries.js` to `npm test`.

Feature flags:

- No new UI feature flags. The CLI's existence implies the `trackBoundaryComputation` capability.

Verification:

- `npm test` passes (all prior + 100 new boundary assertions).
- `npm run build` passes; `dist/compare.html` unchanged (no frontend changes).

Deferred:

- Rendering boundaries in browser compare app (Phase 10).
- Low-confidence styling (Phase 11).
- Diagnostics (Phase 12).
- Gap-filling/interpolation for boundary points where path or width data is missing.
- Smoothing boundary output directly (use smoothed width input instead).