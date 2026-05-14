# Learnings — refactor-main-js

- `renderTrackHeatmapMap()` owned more than rendering: it also owned `ResizeObserver`, map zoom/pan interaction state, and hover state. Moving those together avoided leaking controller internals back into `main.js`.
- The resize callback intentionally had slightly different option semantics from immediate render (`mapSAlignment` was not included, while existing `mapInteraction` state was reused even without checking the feature flag). The extraction preserves that behavior with explicit `buildOpts()` parameters.
- `trackHeatmapMap.js` was also over the 437-line ceiling (511 lines) even though the phase plan assumed only `main.js` was oversized. Splitting canvas drawing primitives into `trackHeatmapDrawing.js` brought every `web/js` module back under the ceiling.
