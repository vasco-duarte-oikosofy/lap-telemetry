# Slice 03 Handoff — Auto-zoom transform

## State on disk

- **`product/web/js/trackHeatmapController.js`** (178 lines): Rewritten with:
  - Re-entrancy guard (`rendering` flag) preventing infinite loop from `setState` → `render()` → `setState`
  - Auto-zoom bounds computed BEFORE `renderWalkingSkeleton`, passed via `buildOpts({ autoZoomBounds })`
  - Removed `mapInteraction` creation for `mapAutoZoom` alone (only `mapZoomPan` creates it)
  - Base transform set after render: segment bounds for auto-zoom, full-track for mapZoomPan

- **`product/web/js/trackHeatmapMap.js`** (223 lines): Added `autoZoomBounds` option to
  `renderWalkingSkeleton`. When set, replaces both `boundsA` and `boundsB` in the
  `fitToView` call, making the canvas render the segment view instead of full-track.

- **`product/dist/compare.html`**: Rebuilt and current.

## Two bugs fixed (discovered after initial commit)

### Bug 1: Infinite loop
`mapInteraction.setState({scale:1,tx:0,ty:0})` triggered `onChange()` → `render()` → `setState()` → infinite loop. Firefox ground to a halt.
**Fix**: `rendering` boolean guard. `render()` delegates to `_render()` inside `try/finally`.

### Bug 2: Auto-zoom had no visual effect
`renderWalkingSkeleton` computed its own `fitToView` from full-track bounds, ignoring
`setBaseTransform`. The `setBaseTransform + setState` approach only affected future
user interactions, not the current paint.
**Fix**: Pass `autoZoomBounds` through `buildOpts` to `renderWalkingSkeleton`. When set,
it replaces both `boundsA` and `boundsB`, so `fitToView` uses segment bounds and the
canvas actually zooms into the segment.

## How to test in the browser

1. Open `product/dist/compare.html` (or use a local server for `product/web/compare.html`)
2. Load a session file
3. Select two laps
4. Enable **both** `mapLinkedHighlight` and `mapAutoZoom` in the feature-flag dropdown
5. Zoom into a distance range on any telemetry chart (drag-select)
6. The map canvas should automatically zoom and pan to frame that segment
7. Reset the chart zoom (double-click or Esc) — the map should return to full-track view
8. The browser should remain responsive (no infinite loop)

## Key architecture

```
render() {
  if (rendering) return;        // re-entrancy guard
  rendering = true;
  try {
    // 1. Compute auto-zoom bounds BEFORE rendering
    autoZoomBounds = computeSegmentBounds(...) → paddedBounds || null;
    
    // 2. Reset user transform if auto-zoom is on (guarded — no infinite loop)
    if (mapAutoZoom && mapInteraction) setState({1,0,0});
    
    // 3. Render with segment bounds (or full-track if null)
    renderWalkingSkeleton(canvas, lapA, lapB, buildOpts({ autoZoomBounds }));
    
    // 4. Set base transform for future user interactions
    if (autoZoomBounds) setBaseTransform(segmentTf);
    else if (mapZoomPan) setBaseTransform(fullTrackTf);
  } finally {
    rendering = false;
  }
}
```

## deferred TODOs

None. This slice's acceptance is now pending visual browser verification.
The Playwright acceptance test belongs to slice 04.