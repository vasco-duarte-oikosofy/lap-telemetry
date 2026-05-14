# Phase 05a — Handoff

## Concrete state

- `npm test` exits 0 (all suites including `test_05a_linked_highlight.js`).
- Feature flag `features.mapLinkedHighlight` is added to `appState.js` (default OFF).
- The canvas map now draws a translucent highlight band when `visibleRange` is provided and the flag is enabled.
- `currentZoomRange` (from `cursor.js` / trace-chart zoom) is passed through `main.js` → `renderTrackHeatmapMap()` → `renderWalkingSkeleton()` as `visibleRange`.

## Files changed in this phase

| File | What changed |
|------|-------------|
| `web/js/appState.js` | Added `mapLinkedHighlight: false` to `features` |
| `web/js/debugHooks.js` | Added `mapLinkedHighlight` to re-render trigger list |
| `web/js/main.js` | Added `mapLinkedHighlight` to `anyMapFeature`; passed `showLinkedHighlight` and `visibleRange: currentZoomRange` in opts |
| `web/js/trackHeatmapMap.js` | Added `drawLinkedHighlight()`; called after ribbon drawing when `showLinkedHighlight && visibleRange` |
| `scripts/test_05a_linked_highlight.js` | New acceptance test |
| `scripts/test_feature_flag_dropdown.js` | Added `mapLinkedHighlight` to `KNOWN_FLAGS` |
| `package.json` | Added `test_05a_linked_highlight.js` to test script |

## Feature flags live

- `mapLinkedHighlight` — default **OFF**.
- When enabled with `mapDualRibbon` and the trace charts supply `currentZoomRange`, the map brightens the corresponding stretch of track using `globalCompositeOperation = 'lighten'` and draws 1px white perpendicular ticks at the band boundaries.

## New helpers worth knowing about

- `drawLinkedHighlight(ctx, lapA, transform, visibleRange, ribbonWidthPx, ribbonGapPx)` — draws the highlight band and boundary ticks. Pure function, no external state.
- `visibleRange` contract: `{ start: number, end: number }` in meters. Absent / undefined = no-op. Full lap = no-op.

## Deferred TODOs

- Click-to-scrub / reverse binding (Phase 5b)
- Auto-pan when highlight is small and off-screen (Phase 6.7)
- Delta coloring inside the highlight band
- Sector boundaries
