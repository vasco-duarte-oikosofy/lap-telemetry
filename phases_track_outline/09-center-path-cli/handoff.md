# Handoff — Phase 09 Center/Path Polyline CLI

State on disk:

- `scripts/export_center_path.js`
  - New CLI script generating binned averaged world positions from recorded sessions.
  - Exports `exportCenterPath({ sessionPaths, trackId, layoutId, outPath, binSizeM, overwrite })` — main async function.
  - Exports `buildPathFromRows(rows, binSizeM)` — pure function returning `{ points, skipped }`.
  - Exports `readPathRows(sessionPath)` — reads `raw_lap_distance_m`, `pos_x_m`, `pos_z_m` from Parquet.
  - CLI: `node scripts/export_center_path.js --out <path.json> --track-id <track> --layout-id <layout> <session.parquet>... [--overwrite]`
  - Binning: `Math.floor(raw_lap_distance_m / binSizeM) * binSizeM` (same rule as width profile).
  - For each bin: averages `pos_x_m` and `pos_z_m` across all samples.
  - Output JSON shape: `{ track_id, layout_id, bin_size_m, points: [{ s_m, x_m, z_m, sample_count }...], summary: { input_rows, skipped_rows } }`
  - Points sorted by increasing `s_m`. No gap-filling — missing bins are simply absent.
  - Overwrite protection: refuses to write if file exists unless `--overwrite` is passed.

- `scripts/test_center_path_export.js`
  - 71 assertions covering all Phase 09 acceptance criteria.
  - Tests: single fixture averaging, same-bin averaging, multi-session accumulation, missing/non-finite field skipping, ascending s_m ordering, no gap-filling, buildPathFromRows pure function, CLI invocation, overwrite refusal, real Spa endurance integration, width-profile command still works.

- `package.json`
  - Added `node scripts/test_center_path_export.js` to `npm test`.

Verification:

- `npm test` passes (all prior + 71 new center path assertions).
- `npm run build` passes; `dist/compare.html` unchanged (no frontend changes).

Feature flags:

- No new UI feature flags. The CLI's existence implies the `trackCenterPathCli` feature.

Deferred:

- Boundary polylines → Phase 09.1.
- Smoothing of the path (keeping raw for now).
- Gap-filling / interpolation for the path.
- Alignment with width profile datasets.
- Browser UI rendering of the path or boundaries.