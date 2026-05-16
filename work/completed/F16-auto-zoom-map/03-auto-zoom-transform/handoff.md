# Slice 03 Handoff — Auto-zoom transform

## State on disk

- **`product/web/js/trackHeatmapController.js`** (186 lines): Re-architected auto-zoom:
  - Re-entrancy guard (`rendering` flag) prevents infinite loop from `setState → render()`
  - Auto-zoom bounds computed BEFORE `renderWalkingSkeleton`, passed via `buildOpts({autoZoomBounds})`
  - `setState({scale:1,tx:0,ty:0})` only called when `autoZooming` is true (active segment)
  - `mapInteraction` NOT created for `mapAutoZoom` alone (only `mapZoomPan` creates it)
  - Base transform: segment bounds when auto-zooming, full-track when `mapZoomPan` is on
  - Removed redundant `mapAutoZoom` interaction creation block

- **`product/web/js/trackHeatmapMap.js`** (223 lines): Added `autoZoomBounds` option to
  `renderWalkingSkeleton`. When set, replaces both `boundsA` and `boundsB` in `fitToView`,
  making the canvas render the segment view.

- **`product/dist/compare.html`**: Rebuilt and current.

## How auto-zoom works now

```
render() {
  if (rendering) return;  // re-entrancy guard
  rendering = true;
  try {
    _render():
      1. Compute autoZoomBounds from computeSegmentBounds(lapA, currentZoomRange)
         - If segment found: autoZoomBounds = padded bounds, autoZooming = true
         - Otherwise: autoZoomBounds = null, autoZooming = false
      2. If autoZooming and mapInteraction exists: setState({1,0,0}) to reset user zoom
      3. renderWalkingSkeleton(canvas, lapA, lapB, buildOpts({autoZoomBounds}))
         - autoZoomBounds replaces fitToView bounds → canvas renders segment view
      4. If autoZooming: setBaseTransform(segment transform)
         Else if mapZoomPan: setBaseTransform(full-track transform)
  } finally {
    rendering = false;
  }
}
```

## Behaviour matrix (corrected)

| mapAutoZoom | mapZoomPan | visibleRange | Result |
|---|---|---|---|
| off | off | any | No change (existing behaviour) |
| off | on | any | Existing manual zoom/pan works |
| on | off | null/full-track | Full-track view, no state changes |
| on | off | partial range | Auto-zooms to segment |
| on | on | null/full-track | Manual zoom/pan works (no reset) |
| on | on | partial range | Auto-zooms to segment, overrides zoom |

## Deferred TODOs

- Resize observer doesn't pass `autoZoomBounds` — on resize, map briefly
  shows full-track then auto-zooms on next render. Acceptable for now.
- Slice 04 will add Playwright acceptance tests.