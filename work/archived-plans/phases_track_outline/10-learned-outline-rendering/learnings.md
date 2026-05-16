# Learnings — Phase 10 Learned Outline Rendering

1. **Boundary data loading uses the same JSON file channel as sidecar/apex annotations.** When a JSON file with `track_id`, `layout_id`, `left` array, and `right` array is loaded (via the file input alongside parquet), it's detected as boundary data and stored in `learnedBoundariesByLayout`. This follows the same pattern as `apexAnnotationsByLayout`.

2. **The `isBoundaryData` check must exclude apex annotations and sidecars.** Apex annotations also have `track_id` and `layout_id` but have `corners` instead of `left`/`right`. The detection function checks for `Array.isArray(obj.left) && Array.isArray(obj.right)` to distinguish.

3. **Zero-width boundary points (`width_m === 0`) are skipped during rendering.** Rather than drawing them as collapsed points on the center path, we break the polyline. This preserves the visual gap at one-sided coverage sections and avoids drawing misleading boundary lines at center-path positions.

4. **Boundaries are drawn as faint cyan rgba(0,255,255,0.35) lines with lineWidth=1.** The alpha is intentionally low — they're a background context layer underneath the track outline and lap ribbons. The draw order is: background → learned boundaries → track outline → lap ribbons.

5. **Track/layout matching uses slug-based keys.** The `boundaryKey()` function slugifies both the session sidecar's track name and the boundary JSON's `track_id` for matching. This handles case/spacing differences between "Circuit de Barcelona" and "circuit-de-barcelona".

6. **The `learnedTrackOutline` feature flag is off by default.** Users must enable it via the feature flag dropdown. The boundary data is loaded and stored even when the flag is off — only the rendering is gated.

7. **The canvas rendering test approach for Phase 10:** The unit tests for `drawLearnedBoundaries` use synthetic transforms (not fit-to-view computed from session data) because boundary fixture coordinates may not overlap with session track coordinates. Integration tests verify flag toggling, data storage, and no crashes, while unit tests verify pixel-level rendering correctness.

8. **Learned boundaries use the same `fitToView` + `applyUserTransform` as lap data.** No separate transform is needed — boundaries go through the same coordinate system, so they zoom/pan correctly with the map.