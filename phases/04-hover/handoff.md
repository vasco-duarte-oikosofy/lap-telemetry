# Phase 04 — Handoff

## Concrete state

- `npm test` exits 0 (all suites including the new `test_04_hover.js`).
- Feature flag `features.mapHover` is added to `appState.js` (default OFF).
- Hover crosshair (white perpendicular tick across both ribbons) and per-lap readout panel implemented.
- Spatial index: uniform grid with 20m cells in `web/js/mapHover.js`.
- Readout DOM (`#map-hover-readout`) created dynamically inside the map panel, positioned absolutely with edge-flipping.
- Pointer events coalesced via `requestAnimationFrame`.
- Readout and tick hidden during drag, reappear on next `pointermove` after drag ends.
- `currentLapBRaw` now includes `throttle` and `brake` arrays (needed for Lap B readout).

## Files changed in this phase

| File | What changed |
|------|-------------|
| `web/js/appState.js` | Added `mapHover: false` to `features` |
| `web/js/debugHooks.js` | Added `mapHover` to re-render trigger list |
| `web/js/main.js` | Added `mapHover` to `anyMapFeature`; wired `showHover`/`hoverState` into opts; added `throttle`/`brake` to `currentLapBRaw`; created `mapHover` controller in `renderTrackHeatmapMap` |
| `web/js/trackHeatmapMap.js` | Exported `getLastTransform`/`setLastTransform`; added `drawHoverTick`; accepts `showHover` and `hoverState` in opts |
| `web/js/mapHover.js` | New module: spatial index, pointermove hit-testing, rAF coalescing, readout DOM create/update/position |
| `web/css/styles.css` | Added `.map-hover-readout`, `.readout-dist`, `.readout-row` styles |
| `scripts/test_04_hover.js` | New acceptance test |
| `scripts/test_feature_flag_dropdown.js` | Added `mapHover` to `KNOWN_FLAGS` |
| `package.json` | Added `test_04_hover.js` to test script |
| `phases/04-hover/` | `learnings.md`, `handoff.md` |

## Feature flags live

- `mapHover` — default **OFF**.
- When enabled with `mapDualRibbon`: hovering over the canvas shows a white perpendicular tick across both ribbons and a small readout near the cursor with per-lap throttle/brake values.
- Readout flips horizontally/vertically near canvas edges to stay on-screen.
- During drag (pan), readout and tick are hidden.

## New helpers worth knowing about

- `createMapHover(canvas, getLapData, onUpdate)` — self-contained hover controller. Builds a uniform-grid spatial index, handles `pointermove`/`pointerleave`/`pointerdown`/`pointerup`, manages the readout DOM, and coalesces updates with rAF.
- `getLastTransform()` / `setLastTransform()` — exported from `trackHeatmapMap.js` so the hover layer can invert screen coordinates back to world space without recomputing the transform.

## Deferred TODOs

- Click-to-pin or multi-point comparison (Phase 5b)
- Statistics / delta numbers beyond throttle/brake
- Linked highlight band (Phase 5a)
