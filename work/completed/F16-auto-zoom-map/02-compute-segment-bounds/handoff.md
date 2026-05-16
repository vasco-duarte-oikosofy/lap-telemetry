# Slice 02 Handoff — Compute segment bounds

## State on disk

- **`product/web/js/trackHeatmapMap.js`** (223 lines): Added `computeSegmentBounds(lapA, visibleRange)` between `applyUserTransform` and `renderWalkingSkeleton`. The function is exported.
- **`dev/scripts/test_f16_segment_bounds.js`**: New Node unit test with 24 assertions over 10 scenarios.
- **`package.json`**: Added `test_f16_auto_zoom.js` and `test_f16_segment_bounds.js` to the test script chain.
- **`product/dist/compare.html`**: Rebuilt and current.

## `computeSegmentBounds` contract

```js
export function computeSegmentBounds(lapA, visibleRange)
```

- `lapA`: `{ x: Float64Array, z: Float64Array }` — track coordinates.
- `visibleRange`: `{ start, end }` — distance values matching `lapA.x` index space.
- Returns `{ minX, maxX, minZ, maxZ }` for the points within the range.
- Returns `null` when:
  - `visibleRange` is `null` or `undefined`
  - No points fall within the range
  - The range covers the entire lap (full-track = no auto-zoom needed)
  - `lapA` is empty or falsy
- Normalizes inverted ranges (`start > end`) by swapping.

## Next slice (03) integration points

Slice 03 will wire `computeSegmentBounds` into `trackHeatmapController.js`:

1. In the `render()` function, after `buildOpts()`, check `features.mapAutoZoom && visibleRange`.
2. Call `computeSegmentBounds(lapA, visibleRange)`.
3. If it returns a bounds object, pad it by 10% on each axis.
4. Call `fitToView(segmentBounds, segmentBounds, rect.width, rect.height, 15)` to get the auto-zoom transform.
5. Call `setBaseTransform(tf)` and `mapInteraction.setState({ scale: 1, tx: 0, ty: 0 })`.

When `mapAutoZoom` is on and `visibleRange` is null, let the normal full-track `fitToView` happen and reset `mapInteraction.setState({ scale: 1, tx: 0, ty: 0 })`.

## Deferred TODOs

None. This slice is complete per acceptance criteria.