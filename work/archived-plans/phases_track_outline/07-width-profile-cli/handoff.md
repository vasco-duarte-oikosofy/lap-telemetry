# Handoff — Phase 07 Width Profile CLI

State on disk:

- `scripts/export_width_profile.js`
  - New optional Node CLI/helper.
  - CLI shape: `node scripts/export_width_profile.js --out <profile.json> --track-id <track> --layout-id <layout> <session1.parquet> [session2.parquet ...] [--overwrite]`
  - Exports `exportWidthProfile({ sessionPaths, trackId, layoutId, outPath, binSizeM, overwrite })` for tests/automation.
  - Reads `raw_lap_distance_m`, `path_lateral_m`, `track_edge_m` from Parquet via `hyparquet`.
  - Binning rule: `Math.floor(raw_lap_distance_m / binSizeM) * binSizeM`; negative `path_lateral_m` → left bin, non-negative → right bin; `max(track_edge_m)` per bin per side.
  - Also exports `buildProfileFromRows(rows, binSizeM)` and `readSessionRows(sessionPath)` for unit testing.
  - Skipped rows (missing/non-finite required fields) counted in `summary.skipped_rows`.
  - Refuses to overwrite existing output unless `overwrite: true` / `--overwrite` is passed.

- `scripts/test_width_profile_export.js`
  - 61 assertions covering all acceptance criteria.
  - Builds synthetic Parquet fixtures with Python/pyarrow.
  - Covers: single-fixture left/right binning, multi-session accumulation, skip counting, overwrite refusal/override, CLI invocation, floor rule, same-bin max, zero-lateral → right, real-session integration (Spa endurance).

- `package.json`
  - Adds `node scripts/test_width_profile_export.js` to `npm test`.

- `phases_track_outline/PLAN`
  - Marks `07-width-profile-cli` DONE.

- `phases_track_outline/CURRENT`
  - Set to `08-width-profile-confidence`.

- `dist/compare.html`
  - Rebuilt with `npm run build`; no frontend source changed in this phase.

Feature flags live:

- No new feature flags. The width profile CLI is optional and command-driven only.
- `features.trackWidthProfileCli` from §0.5 is acknowledged but no UI flag is wired yet; CLI use is enough.

Verification:

- `npm test` passed (all 52 new assertions + all prior assertions).
- `npm run build` passed; no frontend bundle changes.

Deferred:

- Confidence scoring and explicit gap/one-sided flags → Phase 08.
- Smoothing/interpolation → Phase 08.1.
- Center/path polyline → Phase 09.
- Boundary polylines → Phase 09.1.
- Browser UI export buttons or auto-discovery.
- `lap_distance_m` fallback explicitly forbidden by spec for width calculations.