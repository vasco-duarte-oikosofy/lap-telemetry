# Phase 09 — Center/path polyline CLI

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 9 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially:
   - §0.4 Width profile contract (for the paired JSON shape)
   - §0.5 Feature flags / delivery switches
   - "Phase 9 — Center/path polyline CLI"
3. Read prior handoffs:
   - `phases_track_outline/08.1-width-profile-smoothing/handoff.md`
   - `phases_track_outline/08.1-width-profile-smoothing/learnings.md`
4. Inspect nearby code/tests before adding files:
   - `scripts/export_width_profile.js` (CLI pattern, readSessionRows, binning)
   - `scripts/test_width_profile_export.js` (test pattern, Parquet fixture builder)
   - `package.json`
5. Write failing tests first.
6. Implement the center/path polyline CLI.
7. Stop when Phase 09 acceptance passes; do not start boundary polylines, rendering, or diagnostics phases.

**Current state:**

- `phases_track_outline/CURRENT` is `09-center-path-cli`.
- Phase 08.1 completed interpolation and smoothing for width profiles. The width profile CLI (`scripts/export_width_profile.js`) produces JSON with raw + optional smoothed left/right widths per bin, along with `s_m`, sample counts, status, and confidence.
- Width profile JSON includes `track_id`, `layout_id`, `bin_size_m`, `samples[]`, and `summary`. The path JSON should follow a similar shape so the two can be paired.
- The Parquet schema includes `pos_x_m`, `pos_y_m`, and `pos_z_m` for world positions. For 2D track outlines, `pos_x_m` and `pos_z_m` are the horizontal-plane coordinates (y is vertical/up in LMU/rF2). The width profile bins by `raw_lap_distance_m`; the path must use the same binning so the two datasets align by `s_m`.
- Existing `readSessionRows()` in `export_width_profile.js` reads `raw_lap_distance_m`, `path_lateral_m`, `track_edge_m`, and `lap_number`. A new reader (or extended reader) will need `pos_x_m` and `pos_z_m` as well.
- Existing browser/UI behavior should remain unchanged. This phase is CLI/helper driven only.

**Implementation guidance:**

- Create a new script `scripts/export_center_path.js` following the CLI pattern of `export_width_profile.js`.
- CLI shape: `node scripts/export_center_path.js --out <path.json> --track-id <track> --layout-id <layout> <session1.parquet> [session2.parquet ...] [--overwrite]`
- Export a function `exportCenterPath({ sessionPaths, trackId, layoutId, outPath, binSizeM, overwrite })` for tests.
- Read `raw_lap_distance_m`, `pos_x_m`, and `pos_z_m` from Parquet. Rows missing any of these fields are skipped and counted.
- Binning: use same `Math.floor(raw_lap_distance_m / binSizeM) * binSizeM` rule as width profile.
- For each bin, average `pos_x_m` and `pos_z_m` across all samples in that bin.
- Output path JSON shape:
  ```json
  {
    "track_id": "circuit-de-spa-francorchamps-endurance",
    "layout_id": "default",
    "bin_size_m": 1,
    "points": [
      { "s_m": 0, "x_m": -136.94, "z_m": 646.23, "sample_count": 42 },
      ...
    ],
    "summary": {
      "input_rows": 118419,
      "skipped_rows": 0
    }
  }
  ```
- Use `points` (not `samples`) in the path JSON to distinguish from the width profile's `samples`.
- Each point includes `s_m`, averaged `x_m`, averaged `z_m`, and `sample_count` for that bin.
- Points are sorted by increasing `s_m`.
- No gap-filling or interpolation in this phase — only bins with data appear. Gaps simply don't have a point entry. (Phase 9.1 boundary derivation will handle alignment with the width profile.)
- Export `buildPathFromRows(rows, binSizeM)` as a pure function for unit testing (same pattern as `buildProfileFromRows`).
- Export `readPathRows(sessionPath)` for reading pos columns from Parquet.
- Feature flag `features.trackCenterPathCli` from §0.5 — since this is CLI-only, no UI flag is needed yet. The command's existence implies the feature.

**Acceptance criteria:**

- CLI fixture produces expected averaged x/z points by bin.
- Missing position rows are skipped and counted in warnings.
- Output points are ordered by increasing `s_m`.
- Existing width-profile command behavior is unchanged.
- Existing `npm test` remains green.

**Suggested tests:**

- Create a new test file `scripts/test_center_path_export.js` following the existing pattern.
- Include at least:
  - A fixture with known `raw_lap_distance_m`, `pos_x_m`, `pos_z_m` values — assert averaged positions per bin.
  - Multiple samples in the same bin — assert positions are averaged correctly.
  - Multiple input sessions — assert positions accumulate (averaged across sessions).
  - Rows with missing/non-finite position fields — assert they are skipped and counted in `skipped_rows`.
  - CLI invocation — assert exit 0, output is valid JSON with expected shape.
  - Output points ordered by increasing `s_m`.
  - No gap-filling — missing bins are simply absent from `points`.
  - Real session integration (Spa endurance) — smoke test that reads the parquet and produces a path JSON.
- Reuse the `buildParquet` helper from existing test files. Add `pos_x_m` and `pos_z_m` columns to the fixture.

**Out of scope:**

- Boundary polylines (Phase 09.1).
- Normals or offset geometry.
- Smoothing of the path (keep it raw).
- Gap-filling or interpolation.
- Browser UI changes.
- Automatic profile/path discovery.

**When done:**

- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current. If no frontend bundle changes occur, still run the build and document whether `dist/compare.html` changed.
- `phases_track_outline/09-center-path-cli/learnings.md` exists.
- `phases_track_outline/09-center-path-cli/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `09.1-boundary-polylines`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 09.1.