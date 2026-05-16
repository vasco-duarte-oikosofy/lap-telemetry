# Slice 03 Learnings — Auto-zoom transform

## What surprised me

1. **mapInteraction creation must come before renderWalkingSkeleton**: The `mapInteraction` object is needed by `buildOpts()` (which reads `mapInteraction.getState()` for the user transform). Placing the `mapAutoZoom` creation block before `mapHover` and the render call ensures it exists when needed. The creation is guarded by `!mapInteraction`, so if `mapZoomPan` already created it, we don't create a duplicate.

2. **Auto-zoom overrides mapZoomPan's base transform**: When both `mapZoomPan` and `mapAutoZoom` are on, the `mapZoomPan` block sets `setBaseTransform` to the full-track view, then the `mapAutoZoom` block immediately overrides it with the segment view. This is correct — auto-zoom takes precedence when a segment is highlighted. When the range is cleared, the auto-zoom `else` branch just resets the user transform; the full-track base transform from `mapZoomPan` remains untouched, so the map returns to full-track naturally.

3. **The `else` branch (no segment bounds) only resets user transform**: It does NOT call `setBaseTransform` with full-track bounds, because the full-track `setBaseTransform` is already handled either by the `mapZoomPan` block or by the default `renderWalkingSkeleton` behaviour. Resetting only `setState({ scale: 1, tx: 0, ty: 0 })` is sufficient to return to the base transform that's already in place.

4. **`mapAutoZoom` without `mapZoomPan`**: When `mapAutoZoom` is on but `mapZoomPan` is off, the auto-zoom logic creates `mapInteraction` to enable `setState()` for resetting. This means the user gets auto-zoom but no manual zoom/pan. This is intentional per the spec — manual zoom/pan requires `mapZoomPan`.