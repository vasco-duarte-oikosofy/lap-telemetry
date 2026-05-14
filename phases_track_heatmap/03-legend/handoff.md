# Phase 03 — Handoff

## Concrete state

- `npm test` exits 0 (all suites including the new `test_03_legend.js`).
- Feature flag `features.mapLegend` is added to `appState.js` (default OFF).
- Lap legend DOM overlay (`#map-lap-legend`) and color-ramp legend DOM overlay (`#map-ramp-legend`) live in `web/js/mapLegend.js` as `updateMapLegend(panel, lapA, lapB, visible)`.
- Ribbon outer-edge outline (1px accent-color stroke) implemented in `web/js/ribbon.js` inside `drawDualRibbons`.
- CSS for legend overlays added to `web/css/styles.css`.
- `web/js/main.js` wires `showLegend` into `renderWalkingSkeleton` and the ResizeObserver callback.
- `web/js/debugHooks.js` triggers re-render on `mapLegend` flag change.
- `scripts/test_feature_flag_dropdown.js` includes `mapLegend` in `KNOWN_FLAGS`.
- Build script (`npm run build`) produces a working `dist/compare.html`.

## Files changed in this phase

| File | What changed |
|------|-------------|
| `web/js/appState.js` | Added `mapLegend: false` to `features` |
| `web/js/debugHooks.js` | Added `mapLegend` to re-render trigger list |
| `web/js/main.js` | Added `mapLegend` to `anyMapFeature`; wired `showLegend` into opts |
| `web/js/ribbon.js` | Added outer-edge accent-color stroke after each dual-ribbon segment |
| `web/js/mapLegend.js` | New module: creates/updates lap legend + color-ramp legend DOM overlays |
| `web/js/trackHeatmapMap.js` | Imports `updateMapLegend`; calls it at end of `renderWalkingSkeleton` |
| `web/css/styles.css` | Added `.map-legend-overlay`, `.map-lap-legend`, `.map-ramp-legend` styles |
| `scripts/test_03_legend.js` | New acceptance test |
| `scripts/test_feature_flag_dropdown.js` | Added `mapLegend` to `KNOWN_FLAGS` |
| `package.json` | Added `test_03_legend.js` to test script |
| `phases/03-legend/` | `learnings.md`, `handoff.md` |

## Feature flags live

- `mapLegend` — default **OFF**.
- When enabled with `mapDualRibbon`: both lap legend (top-left swatches + labels) and color-ramp legend (top-right 160×16 gradient strip) appear over the canvas.
- Both overlays use `pointer-events: none` so zoom/pan gestures pass through.
- Ribbon outer edges are outlined in accent color regardless of `mapLegend` (drawn whenever `showDualRibbon` is true).

## New helpers worth knowing about

- `updateMapLegend(panel, lapA, lapB, visible)` — idempotent DOM helper. Creates `#map-lap-legend` and `#map-ramp-legend` once, then toggles `display` and updates swatch colors on subsequent calls.
- `drawDualRibbons` now draws two additional `lineTo` strokes per segment after the ribbon fill — one for each lap's outer edge in that lap's accent color.

## Deferred TODOs

- Hover readout (Phase 4)
- Legend statistics / deltas
- Responsive legend font sizing below breakpoint
