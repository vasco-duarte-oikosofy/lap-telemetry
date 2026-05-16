# Phase 07 — Width profile CLI walking skeleton

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 7 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially:
   - §0.1 Raw recorder channels
   - §0.4 Width profile contract
   - §0.5 Feature flags / delivery switches
   - "Phase 7 — Width profile CLI walking skeleton"
3. Read prior handoffs:
   - `phases_track_outline/01-recorder-track-edge-channels/handoff.md`
   - `phases_track_outline/02-loader-new-channels/handoff.md`
   - `phases_track_outline/06-apex-sidecar-export/handoff.md`
4. Inspect nearby code/tests before adding files:
   - `web/js/trackOutlineChannels.js`
   - `scripts/export_apex_metrics.js`
   - `scripts/test_apex_metrics_export.js`
   - `scripts/test_track_outline_loader_channels.js`
   - `package.json`
5. Write failing tests first.
6. Implement the smallest optional CLI/helper that reads one or more Parquet sessions and writes raw, unsmoothed width-profile JSON to an explicit output path.
7. Stop when Phase 07 acceptance passes; do not start confidence scoring, smoothing/interpolation, center path, boundary polylines, rendering, diagnostics, or docs phases.

**Current state:**

- `phases_track_outline/CURRENT` is `07-width-profile-cli`.
- Phase 06 added `scripts/export_apex_metrics.js`, which demonstrates a small Node CLI/helper using `hyparquet` in Node via `asyncBufferFromFile()`, `parquetMetadataAsync()`, and `parquetRead()`.
- `web/js/trackOutlineChannels.js` defines the optional track-outline/apex channel names:
  - `raw_lap_distance_m`
  - `path_lateral_m`
  - `track_edge_m`
  - `distance_to_track_edge_m`
  - surface/terrain wheel channels
- The width-profile CLI must use `raw_lap_distance_m`, `path_lateral_m`, and `track_edge_m` only. Do **not** fall back to `lap_distance_m`.
- Existing browser/UI behavior should remain unchanged. This phase is CLI/helper driven only.
- Recent non-phase polish clarified the Phase 05 apex metrics table; do not expand apex UI work during Phase 07.

**Implementation guidance:**

- Prefer a small Node script/helper similar in spirit to Phase 06, for example:
  - `node scripts/export_width_profile.js --out <profile.json> --track-id <track> --layout-id <layout> <session1.parquet> [session2.parquet ...]`
- Keep output path explicit in this phase. Do not auto-discover or write under `tracks/<track>/<layout>/...` unless the test explicitly needs it.
- Use the §0.4 binning rule exactly:
  - If `path_lateral_m < 0`, update the left bin with `max(left_width_m, track_edge_m)` and increment left sample count.
  - Otherwise, update the right bin with `max(right_width_m, track_edge_m)` and increment right sample count.
- Default `bin_size_m` should be `1` unless an option is added because tests need it.
- Bucket by `raw_lap_distance_m`. A simple `Math.floor(raw_lap_distance_m / bin_size_m) * bin_size_m` bin key is acceptable if documented/tested.
- Skip rows missing required fields or containing non-finite required values. Count skipped rows in a warning/summary field or CLI output; acceptance requires they are not silently ignored.
- Keep the profile raw and unsmoothed. Do not invent confidence beyond what Phase 07 requires; Phase 08 owns confidence/gap semantics.
- Sidecar shape should follow §0.4 and include enough metadata for tests/consumers, for example:
  - `track_id`
  - `layout_id`
  - `bin_size_m`
  - `samples`
  - optional `summary` with input/skipped counts
- Refuse to overwrite an existing output file unless an explicit overwrite option is passed if you follow Phase 06 conventions; if you do, test it.

**Acceptance criteria:**

- CLI/helper test: fixture session produces expected left/right max widths per bin.
- CLI/helper test: multiple input sessions accumulate max widths and sample counts.
- CLI/helper test: rows missing required fields are skipped and counted in a warning summary.
- Output JSON includes `track_id`, `layout_id`, `bin_size_m`, and `samples`.
- Existing compare UI and apex features remain unchanged.
- Existing `npm test` remains green.

**Suggested tests:**

- Add a new Node test such as `scripts/test_width_profile_export.js` and include it in `npm test`.
- Build small synthetic Parquet fixtures inside the test, following the pattern in `scripts/test_apex_metrics_export.js` or `scripts/test_track_outline_loader_channels.js`.
- Include at least:
  - One fixture with negative and non-negative `path_lateral_m` rows proving left/right binning.
  - Two sessions with overlapping bins proving max width and sample-count accumulation.
  - One fixture or rows with missing/non-finite required values proving skipped-row summary behavior.
- Assert exact JSON fields and deterministic numeric values.
- Avoid relying on large real `sessions/` files for acceptance.

**Out of scope:**

- Browser UI export buttons.
- Automatic profile generation during recording or browser loading.
- Confidence scoring or explicit gap statuses beyond a minimal skipped-row summary.
- Smoothing/interpolation.
- Center/path polyline generation.
- Boundary polyline derivation.
- Learned outline rendering.
- Diagnostics reports.
- Any fallback from `lap_distance_m` to `raw_lap_distance_m`.

**When done:**

- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current. If no frontend bundle changes occur, still run the build and document whether `dist/compare.html` changed.
- `phases_track_outline/07-width-profile-cli/learnings.md` exists.
- `phases_track_outline/07-width-profile-cli/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `08-width-profile-confidence`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 08.
