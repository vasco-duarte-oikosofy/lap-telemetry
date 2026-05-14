# Phase 01c — Handoff

## Concrete state

- `npm test` exits 0 (all suites pass, including the new `test_01c_dual_ribbon.js`).
- Feature flag `mapDualRibbon` is added to `appState.js` (`features.mapDualRibbon: false`).
- Dual-ribbon renderer lives in `web/js/ribbon.js` as `drawDualRibbons()`.
- `web/js/trackHeatmapMap.js` imports `drawDualRibbons` and delegates from `renderWalkingSkeleton` when `options.showDualRibbon` is true.
- `web/js/main.js` now passes `currentRefBins?.throttle_norm` and `brake_norm` into `lapB`, enabling Lap B's heatmap colors.
- Re-render triggers (flag toggle, resize) all include `mapDualRibbon`.

## Files changed in this phase

| File | What changed |
|------|-------------|
| `web/js/appState.js` | Added `mapDualRibbon: false` to `features` |
| `web/js/ribbon.js` | New file: extracted `drawRibbon`, `drawHeatmapRibbon`, `darkenHex`, `netAt`, `buildScreenPoints`; added `drawDualRibbons` |
| `web/js/trackHeatmapMap.js` | Removed extracted functions; imports from `ribbon.js`; handles `showDualRibbon` option; draws dual ribbons in correct order |
| `web/js/main.js` | Passes throttle/brake into `lapB`; passes `showDualRibbon`, `ribbonWidthPx`, `ribbonGapPx` to renderer; updated `anyMapFeature` guard |
| `web/js/debugHooks.js` | Added `mapDualRibbon` to re-render trigger list |
| `scripts/test_01c_dual_ribbon.js` | New acceptance test: synthetic canvas render + feature flag exposure |
| `scripts/test_feature_flag_dropdown.js` | Added `mapDualRibbon` to `KNOWN_FLAGS` |
| `package.json` | Added `test_01c_dual_ribbon.js` to test script |
| `phases/01c-dual-ribbon/` | `learnings.md` (this dir) |

## Feature flags live

- `mapDualRibbon` — default **OFF**.
- Can be toggled via the in-page feature-flag dropdown when the canvas map is visible.
- Toggling it on renders both laps as parallel heatmap ribbons on Lap A's centerline.

## New helpers worth knowing

- `drawDualRibbons(ctx, lapA, lapB, transform, widthPx, gapPx)` in `ribbon.js`
  - Builds screen points from **Lap A's** centerline.
  - Computes per-segment normal.
  - Draws Lap A ribbon at `offsetA = -(width+gap)/2`.
  - Draws Lap B ribbon at `offsetB = +(width+gap)/2`.
  - Colors are independently computed from each lap's `throttle`/`brake` arrays via `netAt`.

## Deferred TODOs

- `drawTrackOutline` in `trackHeatmapMap.js` still uses debug magenta/cyan instead of the spec's `rgba(120,120,120,0.4)`. Revisit in a later layout polish subphase.
