# Handoff — Phase 10 Learned Outline Rendering

State on disk:

- `web/js/learnedOutline.js` (new)
  - `isBoundaryData(obj)` — detects boundary JSON (has track_id, layout_id, left[], right[])
  - `boundaryKey(trackId, layoutId)` — slug-based key for matching sessions to boundaries
  - `findBoundaryData(boundariesMap, track, layout)` — lookup by slugged key
  - `drawLearnedBoundaries(ctx, boundaries, transform, style?)` — draws faint left/right polylines on canvas, skipping zero-width points

- `web/js/appState.js`
  - Added `learnedBoundariesByLayout: Map` (stores loaded boundary data)
  - Added `learnedTrackOutline: false` feature flag

- `web/js/ui.js`
  - Added boundary JSON detection in `loadSidecar()` — files with `left`/`right` arrays are stored in `learnedBoundariesByLayout`
  - Added `isBoundaryJson()` check (distinct from `isApexAnnotationJson`)

- `web/js/trackHeatmapMap.js`
  - `renderWalkingSkeleton()` now accepts `learnedBoundaries` and `showLearnedOutline` options
  - Draws boundaries as bottom layer after background fill, before track outline and lap ribbons
  - Boundaries rendered via `drawLearnedBoundaries(ctx, boundaries, transform)`

- `web/js/trackHeatmapController.js`
  - Imports `learnedBoundariesByLayout` and `findBoundaryData`
  - `buildOpts()` resolves boundary data from current session's track/layout via `findBoundaryData()`
  - `anyMapFeature` check now includes `features.learnedTrackOutline`

- `web/js/main.js`
  - Imports `learnedBoundariesByLayout` from appState
  - `getMapState()` includes `learnedBoundariesByLayout`
  - Debug hooks pass `learnedBoundariesByLayout` to `installDebugHooks`

- `web/js/debugHooks.js`
  - Exposes `window.__learnedBoundariesByLayout` for test/debug access
  - `__setFeatureFlag('learnedTrackOutline')` triggers map re-render
  - `window.__renderTrackHeatmapMap` exposed for test-triggered rendering

- `scripts/test_learned_outline_rendering.js` (new)
  - 22 assertions covering:
    - Unit: boundary data detection (isBoundaryData, isBoundaryJson)
    - Unit: drawLearnedBoundaries with empty/null/valid boundaries
    - Unit: faint alpha rendering (alpha < 255)
    - Unit: zero-width points create gaps in drawing
    - Unit: isBoundaryData/import/export functions
    - Unit: findBoundaryData with slug matching
    - Unit: custom transform rendering
    - Integration: feature flag default off, toggle on, data storage
    - Integration: no crash with boundary data enabled but none loaded
    - Integration: no crash with flag enabled and data present

- `package.json`
  - Added `test_learned_outline_rendering` to `npm test`

Feature flags:

- `features.learnedTrackOutline` (default: false) — gates rendering of learned boundaries on the map

Verification:

- `npm test` passes all assertions (22/22 for Phase 10, all prior phases still green)
- `npm run build` succeeds and `dist/compare.html` is current
- `npm run validate` passes all checks

Deferred:

- Low-confidence boundary styling (Phase 11) — dashed/dim segments for low-confidence or one-sided bins
- Automatic boundary file discovery (not yet — user loads JSON explicitly)
- Visual QA with real Spa boundary data (requires loading `data/circuit-de-spa-francorchamps-endurance/default/boundaries.json`)