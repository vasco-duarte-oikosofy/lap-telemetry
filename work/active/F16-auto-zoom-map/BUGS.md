# F16 Auto-Zoom — Bug Log

## Bug 1: Infinite loop (FIXED in commit `58a5550`)
`mapInteraction.setState({scale:1,tx:0,ty:0})` inside `render()` triggered `onChange()` → `render()` → `setState()` → infinite recursion. Firefox ground to a halt.
**Fix**: Re-entrancy guard (`rendering` flag) prevents `render()` from re-entering itself.

## Bug 2: Auto-zoom had no visual effect (FIXED in commit `58a5550`)
`renderWalkingSkeleton` always computed its own `fitToView` from full-track bounds, ignoring `setBaseTransform`. The `setBaseTransform + setState` approach only affected future user interactions, not the current paint.
**Fix**: Added `autoZoomBounds` option to `renderWalkingSkeleton`. When provided, it replaces both `boundsA` and `boundsB` in `fitToView`.

## Bug 3: Map jumps when enabling mapAutoZoom with nothing selected (FIXED in commit `b03369e`)
`setState({scale:1,tx:0,ty:0})` was called unconditionally on every render when `mapAutoZoom` was on, even when no range was selected. This reset any manual zoom/pan, causing the map to jump.
**Fix**: Only call `setState` when `autoZooming` is true (i.e., `computeSegmentBounds` returned actual segment bounds).

## Bug 4: Can't pan/zoom when mapZoomPan is on alongside mapAutoZoom (FIXED in commit `b03369e`)
Same root cause as Bug 3 — unconditional `setState({1,0,0})` on every render overrode user zoom.
**Fix**: Only reset user transform when actively auto-zooming a segment.

## Bug 5: Double-click reset broken when mapAutoZoom is on (OPEN)
When `mapZoomPan` is enabled, double-clicking the map resets zoom (returns to full-track). When `mapAutoZoom` is also enabled, double-click no longer resets. The new feature interferes with existing behaviour. This is an anti-pattern — new features must not break existing ones.
**Probable cause**: The auto-zoom logic sets `setBaseTransform(segmentTf)` on every render, and `setState({1,0,0})` when auto-zooming. Double-click resets the user transform to `{scale:1,tx:0,ty:0}`, but the base transform remains the segment-view transform, so the map stays zoomed into the segment. The auto-zoom code then re-applies the segment transform on the next render cycle, undoing the reset.

## Bug 6: Map moves when enabling mapAutoZoom with nothing selected (OPEN, regression)
When the user toggles `mapAutoZoom` on (with no chart range selected), the map should NOT move. Currently it does — likely because toggling the flag triggers a re-render, and the re-render path applies some transform change even when `computeSegmentBounds` returns null.
**Investigate**: Check if `setBaseTransform` or `setState` is being called when `autoZooming` is false. Also check if the rendering guard or `mapInteraction` creation is causing a visual shift.

## Bug 7: Inconsistent zoom target calculation (OPEN)
When selecting different portions of the telemetry charts, the auto-zoom target appears random — as if a different portion of the track is shown each time, even for the same selection.
**Investigate**: `computeSegmentBounds` uses `lapA.x` as both the X-coordinate AND the distance axis. If `lapA.x[i]` is not the same as the distance values used in `currentZoomRange`, the bounds will be wrong. Need to verify that `visibleRange.start/end` and `lapA.x[i]` are in the same coordinate system.

## Bug 8: Long highlighted portion (e.g., T1 at Fuji) — end of highlight not shown (OPEN)
When a long section of track is highlighted, the auto-zoom doesn't show the end of the highlighted portion. The bounds may be too tight or the padding insufficient.
**Investigate**: Check if the 10% padding is sufficient, or if the `fitToView` call needs adjustment for very elongated segments. Also check if `lapA` (session lap) bounds are representative of `lapB` (reference lap) — if they diverge, only session-portion bounds are used.

## Bug 9: Map moves to show selected portion but does not ZOOM (OPEN)
When selecting a portion of the telemetry charts, the map pans to show the selected area but does not zoom in — the track segment is shown at the same scale as full-track, just centered.
**Investigate**: `autoZoomBounds` may be too wide (e.g., if padding is excessive or the bounds cover a large portion of the track). Also check if `fitToView` with `autoZoomBounds` as both A and B correctly computes a zoomed-in transform. The issue might be that `computeSegmentBounds` returns bounds that are nearly as large as the full track.