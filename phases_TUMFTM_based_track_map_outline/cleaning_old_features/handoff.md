# Handoff — Cleaning Old Features Replaced by TUMFTM Static Outline

State on disk:

- `web/js/learnedOutline.js` — **deleted** (was the entire learned boundary rendering module)
- `scripts/test_006_track_outline.js` — **deleted** (tested removed `mapTrackOutline` feature)
- `scripts/test_learned_outline_rendering.js` — **deleted** (tested removed `learnedTrackOutline` feature)
- `006-test-report/` and `10-test-report/` — **deleted** (stale test artifacts)

Modified files:

- `web/js/appState.js`
  - Removed `mapTrackOutline: true` and `learnedTrackOutline: false` from `features`
  - Removed `learnedBoundariesByLayout` Map export

- `web/js/trackHeatmapController.js`
  - Removed imports: `learnedBoundariesByLayout`, `findBoundaryData`, `store`
  - Removed from `buildOpts()`: `showOutline`, `showLearnedOutline`, `learnedBoundaries` options
  - Removed learned-boundaries resolution loop
  - Added `_currentCursorBinIdx`, `setCursorBinIdx()`, `drawCursorDot()` for canvas cursor dot
  - `buildOpts()` now passes `cursorBinIdx` option
  - `anyMapFeature` guard simplified with comment explaining `|| true`

- `web/js/trackHeatmapMap.js`
  - Removed imports: `drawTrackOutline`, `drawLearnedBoundaries`
  - Removed `showOutline`, `showLearnedOutline`, `learnedBoundaries` options
  - Removed learned-boundaries and track-outline drawing blocks and console.log lines
  - Added `cursorBinIdx` option in `renderWalkingSkeleton()`
  - Added `drawCanvasCursorDot()` — incremental overlay with patch save/restore
  - Added `resetCanvasCursorDotPatch()` — called on full canvas clear
  - Comment header updated (removed stale feature flag references)

- `web/js/trackHeatmapDrawing.js`
  - Removed `drawTrackOutline()` export and `drawOffsetPolyline()` helper
  - All other exports (`drawPolyline`, `drawHoverTick`, `drawLinkedHighlight`, `drawStartFinishTick`, `drawDebugTicks`) remain

- `web/js/debugHooks.js`
  - Removed `window.__learnedBoundariesByLayout` debug hook
  - Removed `mapTrackOutline` and `learnedTrackOutline` from flag-triggered re-render guard

- `web/js/ui.js`
  - Removed imports: `learnedBoundariesByLayout`, `isBoundaryData`, `boundaryKey`
  - Removed `isBoundaryJson()` function and boundary JSON file-type detection in `loadSidecar()`

- `web/js/main.js`
  - Removed `learnedBoundariesByLayout` from appState import
  - Removed `learnedBoundariesByLayout` from `getMapState()` return
  - Removed `learnedBoundariesByLayout` from `installDebugHooks()` deps
  - Added `canvasCursor` parameter to `initCursorAndZoom()` call

- `web/js/cursor.js`
  - Added `canvasCursor` parameter to `initCursorAndZoom()`
  - Added `_currentBinIdx` module variable and `window.__debugGetCursorBinIdx` debug getter
  - `updateCursorDot()` now updates both SVG dot and canvas dot (via controller methods)

- `scripts/test_feature_flag_dropdown.js`
  - Removed `mapTrackOutline` from `KNOWN_FLAGS` array

- `scripts/test_f1f2.js`
  - Added canvas cursor dot assertion (checks `window.__debugGetCursorBinIdx` non-null after hover)

- `package.json`
  - Removed `test_006_track_outline.js` and `test_learned_outline_rendering.js` from test chain

Verification:

- `bash scripts/test-summary.sh` → 732 assertions, 33 scripts, ALL PASS
- `npm run build` succeeds, `dist/compare.html` rebuilt

Feature flags on disk (appState.js features map):

```
mapWalkingSkeleton: true       // canvas renderer — ON
mapHeatmapSingleLap: false     // Phase 01a
mapSAlignment: false           // Phase 01b
mapDualRibbon: false           // Phase 01c
mapZoomPan: false              // Phase 02
mapLegend: false               // Phase 03
mapHover: false                // Phase 04
mapLinkedHighlight: false     // Phase 05a
apexAnnotations: false         // Phase 03 apex
apexMetrics: false             // Phase 04 apex
apexMetricsUi: false           // Phase 05 apex
```

Apex features: all intact, no dependency on removed code, all tests pass.

Deferred:

- Apex adaptation for TUMFTM corner/turn definitions (evaluated but not needed now — parquet schema unchanged)
- Phase 03+ of the TUMFTM plan (offline workflow hardening, manifest/aliases)