# Phase 01a — Heatmap Ribbon, Single Lap Handoff

## Status

✅ COMPLETE on branch `phase/01a-heatmap-single-lap`.

## What changed

- Added `web/js/colorRamp.js`
  - Exports `colorForNet(net)`.
  - Exports `NET_COLOR_LUT` with 256 entries.
  - Exact endpoints: brake `#0a3d91`, neutral `#2a3340`, throttle `#0f7a2e`.
- Updated `web/js/trackHeatmapMap.js`
  - Added exported `drawRibbon()` that fills one quad per segment.
  - Lap A can render as a heatmap ribbon when enabled.
  - Lap B remains the existing 1px polyline.
  - Each ribbon segment draws 1px darker side strokes.
- Updated `web/js/main.js` / `web/js/appState.js`
  - Added `features.mapHeatmapSingleLap` defaulting to `false`.
  - Passes session `throttle_norm` and `brake_norm` bins to the map renderer.
- Refactored oversized `main.js`
  - Moved panel constants to `web/js/panelConfig.js`.
  - Moved browser debug hooks to `web/js/debugHooks.js`.
- Added `scripts/test_01a_heatmap_single_lap.js` and wired it into `npm test`.
- Updated `phases/PLAN` to mark Phase 01a done.

## Verification

- `npm run build` passes.
- `npm test` passes, including the new Phase 01a test.

## Feature flags

- `features.mapHeatmapSingleLap`: default OFF.
- Toggle in browser console with:

```js
window.__setFeatureFlag('mapHeatmapSingleLap', true)
```

## Deferred

- Lap B ribbon remains out of scope until Phase 1c.
- `s`-based alignment remains out of scope until Phase 1b.
- Zoom/pan transform handling remains out of scope until Phase 2.
