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

## Bug 5: Double-click reset broken when mapAutoZoom is on (FIXED)
When `mapZoomPan` is enabled, double-clicking the map resets zoom (returns to full-track). When `mapAutoZoom` is also enabled, double-click no longer resets. The new feature interfered with existing behaviour. This is an anti-pattern — new features must not break existing ones.
**Root cause**: Auto-zoom is a render-level bounds change, not `mapInteraction` scale. Double-click reset correctly set the user transform to `{scale:1,tx:0,ty:0}`, but the next render still passed `autoZoomBounds`, so the canvas continued fitting only the selected segment at apparent `1x`.
**Fix**: `createMapInteraction` now accepts an `onReset` callback. The controller suppresses auto-zoom for the current chart range when the user double-clicks, passes `autoZoomBounds: null`, and uses full-track bounds until the chart range changes. The chart zoom range remains selected.

## Bug 6: Map moves when enabling mapAutoZoom with nothing selected (OPEN, regression)
When the user toggles `mapAutoZoom` on (with no chart range selected), the map should NOT move. Currently it does — likely because toggling the flag triggers a re-render, and the re-render path applies some transform change even when `computeSegmentBounds` returns null.
**Investigate**: Check if `setBaseTransform` or `setState` is being called when `autoZooming` is false. Also check if the rendering guard or `mapInteraction` creation is causing a visual shift.

## Bug 7: Inconsistent zoom target calculation (OPEN)
When selecting different portions of the telemetry charts, the auto-zoom target appears random — as if a different portion of the track is shown each time, even for the same selection.
**Investigate**: `computeSegmentBounds` uses `lapA.x` as both the X-coordinate AND the distance axis. If `lapA.x[i]` is not the same as the distance values used in `currentZoomRange`, the bounds will be wrong. Need to verify that `visibleRange.start/end` and `lapA.x[i]` are in the same coordinate system.

## Bug 8: Long highlighted portion (e.g., T1 at Fuji) — end of highlight not shown (OPEN)
When a long section of track is highlighted, the auto-zoom doesn't show the end of the highlighted portion. The bounds may be too tight or the padding insufficient.
**Investigate**: Check if the 10% padding is sufficient, or if the `fitToView` call needs adjustment for very elongated segments. Also check if `lapA` (session lap) bounds are representative of `lapB` (reference lap) — if they diverge, only session-portion bounds are used.

## Bug 9: Map moves to show selected portion but does not ZOOM (FIXED)
When selecting a portion of the telemetry charts, the map pans to show the selected area but does not zoom in — the track segment is shown at the same scale as full-track, just centered.
**Root cause**: `computeSegmentBounds` used `lapA.x[i]` (X coordinate) as the distance filter instead of using the array index. This caused incorrect bounds calculation.
**Fix**: Changed `computeSegmentBounds` to use index-based distance filtering. Since resampled track data uses 1m bins, index `i` corresponds to distance `i` metres. The function now filters by `i >= start && i <= end` instead of `lapA.x[i] >= start && lapA.x[i] <= end`.

## Bug 10: mapAutoZoom blocks mapZoomPan panning when a selection is active (FIXED)
When both `mapAutoZoom` and `mapZoomPan` are enabled with a chart zoom range selected, the user cannot pan or zoom the map. Every render resets the user transform to `{scale:1, tx:0, ty:0}`, undoing any user interaction.
**Root cause**: The controller called `mapInteraction.setState({scale:1, tx:0, ty:0})` on EVERY render when auto-zoom was active, not just when the zoom range changed.
**Fix**: Track the previous zoom range (`prevAutoZoomRange`) and only reset the user transform when the range actually changes. This allows users to pan/zoom on top of the auto-zoomed view. When the range changes, the transform resets so auto-zoom snaps to the new segment.

## Bug 11: Auto-zoom doesn't update when zoom range changes within a selection (FIXED)
When the user selects a portion of the lap (auto-zoom activates), then changes to a different portion of the track, the map does not re-zoom to show the new portion. The map stays at the previous auto-zoom position.
**Root cause**: Same as Bug 7 — `computeSegmentBounds` used X coordinates as distance, so changing the zoom range didn't produce different bounds (or produced wrong bounds). The auto-zoom was computing bounds, but they were incorrect.
**Fix**: Same fix as Bug 7 — index-based distance filtering in `computeSegmentBounds`. Now when the zoom range changes, the correct segment bounds are computed and the map re-zooms to show the new portion.

## Bug 12: Cannot zoom OUT when auto-zoom is active (FIXED)
When auto-zoom is enabled and has zoomed into a track segment, the user can pan and zoom IN further, but could not zoom OUT to see more of the track or the full track. The zoom-out gesture appeared to do nothing.
**Root cause**: Auto-zoom fits the selected segment as the base view, while user zoom composes on top of that base. At apparent `1x`, only the selected segment is shown. `mapInteraction.js` clamped user scale at `MIN_SCALE = 1`, so wheel/scroll/pinch could not reduce the user scale below the segment-fit view.
**Fix**: `createMapInteraction` now accepts `getMinScale()`. The track heatmap controller computes a dynamic lower bound while active auto-zoom is fitting a selected segment: `fullTrackFitScale / autoZoomFitScale`. Normal full-track mode still uses `minScale = 1`, while active auto-zoom allows user scale below `1.0` only as far as needed to reveal full-track scale without excessive empty canvas.
**Validation**: `dev/scripts/test_f16_bug12_zoom_out_autozoom.js` verifies full-track mode still clamps at `1`, active auto-zoom starts at user scale `1`, wheel-out lowers scale below `1`, and the rendered canvas changes from the selected-segment view.
