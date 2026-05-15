# Handoff — Phase 01 Static Outline Contract

State on disk:

- `data/track-outlines/spa-francorchamps.json`
  - Production static Spa outline artifact.
  - `schema_version: 1`.
  - Contains 1401-point `centerline`, `left_boundary`, and `right_boundary` arrays in simulator `x/y` coordinates.
  - Uses accepted transform: scale `0.998`, rotation `0.0004`, translate `(-164, 632)`, no flips, `reverse_point_order: true`.
  - Includes caveats that TUMFTM widths are approximate, non-official, and not authoritative simulator track limits.
  - Includes `track_name_mapping` metadata for known Spa/LMU name variants. No runtime lookup is implemented.

- `scripts/test_static_track_outline_contract.js`
  - Deterministic contract test for the Spa artifact.
  - Validates schema version, required metadata, mapping metadata, finite point arrays, matching array lengths, and caveat wording.
  - Added to `npm test`.

- `phases_TUMFTM_based_track_map_outline/PLAN`
  - Phase 01 marked done.

Verification:

- `node scripts/test_static_track_outline_contract.js` passes.
- `npm test` passes.
- `npm run build` passes and rewrote `dist/compare.html`.

Runtime/UI status:

- No compare UI rendering integration was added.
- No manifest file, alias lookup, fuzzy matching, or runtime TUMFTM parsing was added.
