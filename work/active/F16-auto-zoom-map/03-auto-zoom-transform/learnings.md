# Slice 03 Learnings — Auto-zoom transform

## What surprised me

### Initial implementation had two critical bugs

**Bug 1: Infinite loop.** `mapInteraction.setState({scale:1,tx:0,ty:0})` inside `render()`
triggered `onChange()` → `render()` → `setState()` → infinite recursion. Firefox ground to
a halt. **Fix**: re-entrancy guard (`rendering` flag) prevents `render()` from re-entering
itself. `render()` delegates to `_render()` inside `try/finally`.

**Bug 2: Auto-zoom had no visual effect.** `renderWalkingSkeleton` always computed its own
`fitToView` from full-track bounds internally. The `setBaseTransform + setState` approach
only affected future `mapInteraction` references, not the current canvas paint.
**Fix**: added `autoZoomBounds` option to `renderWalkingSkeleton`. When provided, it replaces
both `boundsA` and `boundsB` in `fitToView`, so the canvas actually renders the segment view.

### Second round of bug fixes (user-reported)

**Bug 3: Map jumps when enabling mapAutoZoom with nothing selected.** The original code
called `setState({scale:1,tx:0,ty:0})` unconditionally when `mapAutoZoom` was on,
even when no range was selected. This reset any manual zoom/pan, causing the map to
jump. **Fix**: only call `setState` when `autoZooming` is true (i.e., when there's an
actual segment). When `computeSegmentBounds` returns null (no range / full-track),
leave the user transform untouched.

**Bug 4: Can't pan/zoom when mapZoomPan is on alongside mapAutoZoom.** Same root cause as
Bug 3 — `setState({1,0,0})` was called every render, overriding user zoom constantly.
**Fix**: `setState` only called when actively auto-zooming. When there's no range, user
zoom/pan is preserved.

**Bug 5: Map still didn't zoom into segment (visual).** The original implementation placed
the auto-zoom logic after `renderWalkingSkeleton`, so the canvas was painted with
full-track bounds before auto-zoom could affect it. Moving the auto-zoom computation
BEFORE rendering (into `autoZoomBounds` passed via `buildOpts`) was necessary but not
sufficient on its own — the `autoZoomBounds` must also be passed through
`renderWalkingSkeleton`'s options to replace the bounds in `fitToView`.

### Key insight: rendering vs. base transform

`setBaseTransform()` does NOT affect what `renderWalkingSkeleton` draws. It only
affects future user zoom/pan calculations. To make the canvas actually zoom, we must
pass the segment bounds through the rendering pipeline via `autoZoomBounds`. The
`setBaseTransform` call is still needed (for correct user zoom/pan relative to the
auto-zoomed view), but it doesn't control the current paint.

### mapInteraction not needed for mapAutoZoom alone

When `mapAutoZoom` is on without `mapZoomPan`, there's no user zoom/pan on the canvas.
`buildOpts()` returns `{scale:1,tx:0,ty:0}` by default. No `mapInteraction` is created.
This is simpler and avoids unnecessary event listeners.