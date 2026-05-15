# Handoff — Phase 02 Runtime Static Outline Rendering

State on disk:

- `web/js/staticSpaOutlineData.js`
  - Runtime JS copy of `data/track-outlines/spa-francorchamps.json`.
  - Kept to 3 lines so the large 1401-point artifact remains within file line-count limits.
  - Tested for parsed equality against the source artifact.

- `web/js/staticTrackOutline.js`
  - Small runtime helper for the explicit Spa static outline.
  - Validates schema v1 and finite `left_boundary`, `right_boundary`, and `centerline` arrays.
  - Renders SVG polylines with identifiable `data-static-track-outline` and `data-static-outline-part` attributes.

- `web/compare.html`
  - Adds `<g id="static-track-outline"></g>` as the first child of `#circuit-map-svg`.
  - This places the static outline behind heatmap segments, the existing trajectory outline, zoom arc, and cursor dot.

- `web/js/circuitMap.js`
  - Imports the explicit Spa static outline helper.
  - Renders the static outline on every circuit-map render using the existing trajectory-derived map transform.
  - Existing trajectory map rendering and heatmap mode rendering are preserved.

- `web/css/styles.css`
  - Adds subdued styling for static boundaries and dashed centerline.

- `scripts/test_static_outline_runtime_rendering.js`
  - Confirms runtime Spa data matches `data/track-outlines/spa-francorchamps.json`.
  - Confirms schema v1 is exposed and the SVG helper renders left/right/centerline parts.

- `scripts/test_static_outline_compare_ui.js`
  - Playwright test that loads a Spa session, compares two laps, and verifies the static outline appears in the compare UI behind existing map layers.

- `package.json`
  - Adds both new Phase 02 tests to `npm test` immediately after the existing static artifact contract test.

Verification:

- `node scripts/test_static_track_outline_contract.js` passes.
- `node scripts/test_static_outline_runtime_rendering.js` passes.
- `node scripts/test_static_outline_compare_ui.js` passes.
- `npm test` passes.
- `npm run build` passes and rewrote `dist/compare.html`.

Runtime/UI status:

- The Spa static outline renders behind existing trajectories in the compare UI.
- No manifest, alias lookup, fuzzy matching, automatic track/layout selection, runtime TUMFTM parsing, runtime alignment math, runtime width scaling, or editor behavior was added.

Deferred:

- Phase 03 should harden the offline conversion workflow only.
- Phase 04 should handle manifest and conservative aliases later.
