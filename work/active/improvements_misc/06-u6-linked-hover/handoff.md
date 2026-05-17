# Handoff — U6 Linked Hover

## State on disk

The `0c09bf0` parallel linked-hover path has been replaced with a single coherent
map-hover implementation.

Changed files:

- `product/web/js/appState.js`
  - Keeps `features.mapLinkedHover`.
  - Removed `state.linkedHoverDist`; linked hover no longer uses global app state.

- `product/web/js/cursor.js`
  - No longer imports `features`.
  - No longer mutates linked-hover state or calls a map-render callback directly.
  - Reports chart cursor distance through the third `initCursorAndZoom()` callback.
  - Reports `null` when the cursor leaves the plot, moves outside the plot bounds,
    or starts a drag selection.

- `product/web/js/mapHover.js`
  - Added `setLinkedDistance(s)` and `clearLinkedDistance()`.
  - Direct pointer hover and chart-linked hover now share the same hover-state and
    readout application path.
  - Linked hover creates the same state shape as pointer hover:
    `{ s, screenX, screenY, lapASample, lapBSample, nearest }`.
  - Direct map pointer hover takes priority over linked chart hover.

- `product/web/js/trackHeatmapController.js`
  - Removed linked-hover `sLookup` and global-state logic.
  - Removed `linkedHoverState` / `showLinkedHover` options.
  - Added `setChartHoverDistance(s)` to delegate chart distances to `mapHover`.
  - Still passes only one hover option to the renderer: `hoverState`.

- `product/web/js/trackHeatmapMap.js`
  - Removed the second linked-hover-specific `drawHoverTick()` call.
  - Renderer is source-agnostic again: one `options.hoverState` path draws hover.

- `product/web/js/main.js`
  - Wires `trackHeatmapController.setChartHoverDistance` into `initCursorAndZoom()`.

- `dev/scripts/test_04_hover.js`
  - Added regression coverage that linked chart hover reuses `mapHover` readout,
    direct pointer hover wins, and linked clear hides the readout.

- `product/dist/compare.html`
  - Rebuilt with `npm run build`.

## Activation

Both feature flags must be enabled:

```js
__setFeatureFlag('mapHover', true);
__setFeatureFlag('mapLinkedHover', true);
```

## Behaviour now

Hovering over chart panels reports the chart cursor distance to the map hover
controller. `mapHover.js` turns that distance into the normal map hover UI, so the
canvas map shows both:

- the perpendicular hover tick, and
- the floating throttle/brake readout box.

Direct map hover remains authoritative while the pointer is over the map.

## Verification

- `bash scripts/test-summary.sh dev/scripts/test_04_hover.js` — 22 assertions pass.
- `npm run build` — succeeds and updates `product/dist/compare.html`.
- `bash scripts/test-summary.sh` — 1081 assertions across 45 scripts pass.

## Deferred

None for this slice.
