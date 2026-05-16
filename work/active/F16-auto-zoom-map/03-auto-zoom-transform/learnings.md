# Slice 03 Learnings — Auto-zoom transform

## What surprised me

1. **Infinite loop from setState inside render**: `mapInteraction.setState()` calls
   `trigger()` which calls `render()`, which calls `setState()` again → infinite loop.
   **Fix**: added a `rendering` guard flag that prevents re-entrant `render()` calls.
   `render()` now delegates to `_render()` wrapped in `try/finally` that sets/clears the flag.

2. **setBaseTransform + setState don't affect what renderWalkingSkeleton draws**:
   `renderWalkingSkeleton` computes its own `fitToView(boundsA, boundsB, ...)` from
   full-track bounds internally. Calling `setBaseTransform()` and `setState()` after
   rendering only affects the _next_ render's `mapInteraction` reference — the current
   frame has already been painted with full-track bounds.
   **Fix**: added `autoZoomBounds` option to `renderWalkingSkeleton`. When provided,
   it replaces both `boundsA` and `boundsB` in the `fitToView` call, so the canvas
   actually renders the segment view.

3. **Auto-zoom must be computed BEFORE renderWalkingSkeleton**: Originally the
   auto-zoom logic was placed after `renderWalkingSkeleton`, which meant the first
   frame always showed full-track. Moving it before `render()` (into `buildOpts`
   via `autoZoomBounds`) ensures the correct view is rendered on the first paint.

4. **mapInteraction not needed for mapAutoZoom alone**: Removed the block that
   created `mapInteraction` when only `mapAutoZoom` is on. Without `mapZoomPan`,
   there's no user zoom/pan on the canvas, and `buildOpts()` returns `{scale:1, tx:0, ty:0}`
   by default. The `mapInteraction` is only needed when `mapZoomPan` is on.

5. **When both mapZoomPan and mapAutoZoom are on**: The `mapZoomPan` block sets
   the full-track base transform, but with `autoZoomBounds` present, `renderWalkingSkeleton`
   uses the segment bounds instead. The `setBaseTransform(segmentTf)` in the auto-zoom
   block then overrides the base for future user interactions. User state is reset to
   `{1,0,0}` via `setState`, but the re-entrancy guard prevents the infinite loop.