# Slice 03 — Auto-zoom transform when flag is on

## Goal

When both `mapLinkedHighlight` and `mapAutoZoom` are enabled and a
`visibleRange` is present (non-full-track), the map canvas automatically
zooms and pans to frame the highlighted track segment. When the range is
cleared (zoom reset), the map resets to the default full-track view. This
slice wires the auto-zoom behaviour end-to-end — no new tests beyond the
existing test suite passing, since the interactive Playwright acceptance
test belongs to slice 04.

## Context

### What's already in place

- **`mapAutoZoom: false`** feature flag in `appState.js` (slice 01).
- **`computeSegmentBounds(lapA, visibleRange)`** in `trackHeatmapMap.js`
  (slice 02). Returns `{ minX, maxX, minZ, maxZ }` for points within the
  range, or `null` for full-track / null / empty ranges.
- **`fitToView(boundsA, boundsB, w, h, padding)`** in `trackHeatmapMap.js`.
  Already used for full-track view — computes scale/offset to fit both
  bounding boxes into the canvas.
- **`setBaseTransform(tf)`** and **`createMapInteraction(canvas, onChange)`**
  in `mapInteraction.js`. `setBaseTransform` sets the reference for
  wheel/drag zoom. `mapInteraction.setState({ scale, tx, ty })` resets the
  user transform. `window.__mapZoomPanState` exposes the state for tests.
- **`trackHeatmapController.js`** already imports `features`, `setBaseTransform`,
  `fitToView`, and `computeTrackBounds`. The `render()` function already has
  the pattern for computing full-track `fitToView` and calling
  `setBaseTransform(tf)` when `mapZoomPan` is on.

### How `render()` currently works

The controller's `render()` function:

1. Gets the canvas and SVG elements. Shows canvas, hides SVG.
2. Creates `mapInteraction` (once) when `mapZoomPan` is on.
3. Creates `mapHover` (once) when `mapHover` is on.
4. Gets track data from `getMapState()`, calls `buildLaps()` and
   `buildOpts()`, then calls `renderWalkingSkeleton()`.
5. After rendering, if `mapZoomPan` is on, computes full-track
   `fitToView(boundsA, boundsB, ...)` and calls `setBaseTransform(tf)`.

The auto-zoom logic must be inserted **after** `renderWalkingSkeleton()`
and **alongside** the existing `mapZoomPan` base-transform logic. The key
insight: both `mapZoomPan` and `mapAutoZoom` call `setBaseTransform()`,
but they set it to different transforms. When `mapAutoZoom` is on and
there's a visible range, the base transform should be the segment bounds
(not the full-track bounds).

### Dependency constraint

`mapAutoZoom` depends on `mapLinkedHighlight`. If `mapLinkedHighlight` is
off, there is no highlight and no segment to frame — so `mapAutoZoom`
should have no visible effect. This is enforced naturally by the spec:
`computeSegmentBounds` returns `null` for full-track ranges, and the
controller only auto-zooms when `computeSegmentBounds` returns a non-null
result.

## Steps

1. **Import `computeSegmentBounds` in `trackHeatmapController.js`.** Add it
   to the import from `./trackHeatmapMap.js`.

2. **Add auto-zoom logic to the `render()` function**, after the call to
   `renderWalkingSkeleton(canvas, lapA, lapB, buildOpts())` and after
   the existing `if (features.mapZoomPan)` block. The logic is:

   ```js
   // F16: Auto-zoom to highlighted segment
   if (features.mapAutoZoom && lapA && lapA.x) {
     const { currentZoomRange } = getMapState();
     const segBounds = computeSegmentBounds(lapA, currentZoomRange);
     if (segBounds) {
       // Add 10% padding on each axis
       const dx = (segBounds.maxX - segBounds.minX) || 1;
       const dz = (segBounds.maxZ - segBounds.minZ) || 1;
       const padX = dx * 0.1;
       const padZ = dz * 0.1;
       const paddedBounds = {
         minX: segBounds.minX - padX,
         maxX: segBounds.maxX + padX,
         minZ: segBounds.minZ - padZ,
         maxZ: segBounds.maxZ + padZ,
       };
       const rect = canvas.getBoundingClientRect();
       const tf = fitToView(paddedBounds, paddedBounds, rect.width, rect.height, 15);
       setBaseTransform(tf);
       if (mapInteraction) mapInteraction.setState({ scale: 1, tx: 0, ty: 0 });
     } else {
       // No segment bounds (full-track or null range) → reset to default view
       if (mapInteraction) mapInteraction.setState({ scale: 1, tx: 0, ty: 0 });
     }
   }
   ```

   Important details:
   - `fitToView` is called with `paddedBounds` as **both** arguments (same
     bounds for A and B), since we only want to fit the segment, not both
     laps' full tracks.
   - The existing `if (features.mapZoomPan)` block still runs when
     `mapZoomPan` is on, but when `mapAutoZoom` is also on, the auto-zoom
     block overrides the base transform afterwards. This is correct because
     auto-zoom should take precedence over full-track fit when a segment is
     highlighted.
   - The `else` branch (no segment bounds) resets the user transform so
     that the map returns to full-track view. The full-track `setBaseTransform`
     is already handled by the `mapZoomPan` block or by the default
     `renderWalkingSkeleton` behaviour.

3. **Ensure `mapInteraction` exists when `mapAutoZoom` is on.** Currently
   `mapInteraction` is only created when `mapZoomPan` is on. When
   `mapAutoZoom` is on but `mapZoomPan` is off, we still need
   `mapInteraction` to call `setState()` for resetting the transform.
   Add a creation block for `mapAutoZoom` analogous to the `mapZoomPan`
   one — but **without** creating the zoom indicator UI (that belongs to
   `mapZoomPan`). The minimal version: if `mapAutoZoom` is on and
   `mapInteraction` is null, create it.

   Add this right after the `mapZoomPan` interaction-creation block:

   ```js
   if (features.mapAutoZoom && !mapInteraction) {
     mapInteraction = createMapInteraction(canvas, () => render());
   }
   ```

4. **Run `bash scripts/test-summary.sh`.** All existing tests must still
   pass. The auto-zoom logic is gated behind `features.mapAutoZoom`
   (default `false`), so no existing behaviour changes.

5. **Run `npm run build`.** Must succeed.

6. **Commit.**

## Acceptance

- When `mapAutoZoom` is **off** (default): no change to existing behaviour.
  All existing tests pass.
- When `mapAutoZoom` is **on** and a `visibleRange` is present:
  - `computeSegmentBounds` is called on `lapA`.
  - If it returns bounds, `fitToView` is called with padded bounds, and
    `setBaseTransform` + `setState({ scale: 1, tx: 0, ty: 0 })` are applied.
  - The map frames the highlighted segment with 10% padding.
- When `mapAutoZoom` is **on** and `visibleRange` is null/full-track:
  - The map resets to full-track view
    (`setState({ scale: 1, tx: 0, ty: 0 })`).
- `mapInteraction` is created when `mapAutoZoom` is on, even if
  `mapZoomPan` is off.
- Existing test suite passes: `ALL PASS`.
- Build succeeds: `npm run build`.

## Non-goals

- No Playwright test for auto-zoom behaviour (that's slice 04).
- No changes to `computeSegmentBounds`, `mapInteraction.js`, or
  `trackHeatmapMap.js` rendering logic.
- No UI for toggling auto-zoom beyond the existing feature-flag dropdown.
- Do not change how `visibleRange` is computed — that's existing behaviour.