# Handoff — refactor-main-js

## State on disk

- Branch: `phase/refactor-main-js`
- `web/js/main.js`: 389 lines; still owns data preparation and `renderAll()` orchestration.
- New `web/js/trackHeatmapController.js`: 137 lines; owns canvas map render orchestration, resize observer, hover controller, and map interaction controller.
- New `web/js/trackHeatmapDrawing.js`: 256 lines; owns canvas drawing primitives used by `trackHeatmapMap.js`.
- `web/js/trackHeatmapMap.js`: 180 lines; now focuses on transforms, `renderWalkingSkeleton()`, and resize setup.
- `NEXT_STEPS.md` module table is current and the urgent `main.js` warning was removed.
- `dist/compare.html` was rebuilt with `npm run build`.

## API notes

- `createTrackHeatmapController(getMapState)` returns `{ render(), getMapInteractionState(), getMapHoverState() }`.
- `main.js` keeps the public debug hook callback name via `renderTrackHeatmapMap()`, which delegates to `trackHeatmapController.render()`.
- `getMapState()` supplies the controller with current track arrays, bins, raw lap arrays, and zoom range.

## Verification

- `npm test` passed.
- `npm run build` passed.
- Line ceiling verified with `wc -l web/js/*.js`: all `web/js` modules are ≤ 437 lines.

## Deferred TODOs

- No behavior TODOs were added. Optional future cleanup remains debug-hook isolation if it becomes useful.
