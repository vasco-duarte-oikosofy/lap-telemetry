# Phase 02 — Handoff

## Concrete state

- `npm test` exits 0 (all suites including the new `test_02_zoom_pan.js`).
- Feature flag `features.mapZoomPan` is added to `appState.js` (default OFF).
- Zoom/pan interaction lives in `web/js/mapInteraction.js` as `createMapInteraction(canvas, onChange)`.
- `web/js/trackHeatmapMap.js` exports `applyUserTransform(base, userScale, userPanX, userPanY)` to compose fit-to-view with user pan/zoom.
- `web/js/main.js` eagerly initializes `mapInteraction` when `features.mapZoomPan` is true, passes current zoom/pan into `renderWalkingSkeleton`, and updates `setBaseTransform()` on every render.
- `web/js/debugHooks.js` includes `mapZoomPan` in re-render triggers.
- `scripts/test_feature_flag_dropdown.js` includes `mapZoomPan` in `KNOWN_FLAGS`.
- `scripts/test_02_zoom_pan.js` acceptance test covers:
  - feature flag exposure
  - synthetic transform composition
  - ribbon thickness constancy at scale 1/10/40
  - Playwright wheel-zoom, pointer-drag, and dblclick-reset interactions
  - 2-second 60Hz perf test (p99 ≤ 16ms)
- Build script (`npm run build`) produces a working `dist/compare.html`.

## Files changed in this phase

| File | What changed |
|------|-------------|
| `web/js/appState.js` | Added `mapZoomPan: false` to `features` |
| `web/js/mapInteraction.js` | New module: pointer events, wheel zoom, dblclick reset, zoom indicator updates |
| `web/js/trackHeatmapMap.js` | Added `applyUserTransform`; `renderWalkingSkeleton` accepts `userScale/userPanX/userPanY` |
| `web/js/main.js` | Imports `createMapInteraction`/`setBaseTransform`; wires interaction init and transform passing |
| `web/js/debugHooks.js` | Added `mapZoomPan` to re-render trigger list |
| `web/css/styles.css` | Added `cursor: grab`, `touch-action: none`, and `.map-zoom-indicator` styles |
| `scripts/test_02_zoom_pan.js` | New acceptance test |
| `scripts/test_feature_flag_dropdown.js` | Added `mapZoomPan` to `KNOWN_FLAGS` |
| `package.json` | Added `test_02_zoom_pan.js` to test script |
| `phases/02-zoom-pan/` | `learnings.md`, `handoff.md` |

## Feature flags live

- `mapZoomPan` — default **OFF**.
- When enabled: canvas supports wheel-zoom (clamped [1, 40]), drag-to-pan, dblclick reset, and displays a zoom indicator.
- Ribbon thickness stays constant in screen pixels at all zoom levels.

## New helpers worth knowing about

- `createMapInteraction(canvas, onChange)` — returns `{ getState, setState, destroy }`. State shape: `{ scale, tx, ty }`.
- `applyUserTransform(base, userScale, userPanX, userPanY)` — returns a transform object with composed `toScreenX/Y`.
- `setBaseTransform(transform)` — call this from the renderer so zoom-to-cursor uses the correct base offset.

## Deferred TODOs

- Zoom button stack (Phase 6.5)
- Keyboard shortcuts (Phase 6.4)
- Minimap (Phase 6.6)
- Highlight band (Phase 5a)
- Hover readout (Phase 4)
- Legend (Phase 3)
