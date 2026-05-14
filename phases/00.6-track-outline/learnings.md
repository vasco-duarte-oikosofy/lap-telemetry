# Phase 00.6 — Track Outline Background (Learnings)

## Summary

**Status:** ✅ COMPLETE  
**Feature flag:** `features.mapTrackOutline` (default: OFF)  
**Branch:** `phase/00.6-track-outline`

## What Surprised Us

1. **Grey pixel detection is noisy.** The track outline color (rgba(120, 120, 120, 0.4)) blends with the background and lap polylines, making pixel-based color verification imprecise. The test samples show colors like (124, 141, 114) which are "grey-ish" but not exact matches due to alpha compositing.

2. **Alpha compositing affects color sampling.** When the outline is drawn on a dark background (rgba(0, 0, 0, 0.2)), the resulting pixel color differs from the spec's rgba(120, 120, 120, 0.4). Tests need to account for this by using wider tolerances.

3. **Outline pixel count is high.** The track outline produces a large number of grey pixels (~1.3M at 2x DPR) because it traces the entire circuit. This makes it easy to detect but also means the outline dominates the "grey pixel" category in color analysis.

4. **Offset polyline jitter in high-curvature areas.** Computing parallel offset lines from a racing line produces visible artifacts in tight corners (e.g., Eau Rouge, La Source hairpin). The tangent vector calculation is unstable when:
   - Sample density is high relative to curvature
   - Direction changes are rapid (chicanes, hairpins)
   - Elevation changes affect the 2D projection
   
   We tried multiple fixes:
   - Increased look-ahead from 1 to 5 samples (helped, but didn't eliminate)
   - Adaptive distance-based look-ahead (made it worse)
   - Moving average smoothing (helped, but trades accuracy for smoothness)
   
   **Root cause:** Offset polylines are fundamentally fragile for this use case. The proper solution is ribbon rendering with quads (Phase 1a/1c), which doesn't rely on computing offset tangents.
   
   **Decision:** Accept minor artifacts for Phase 00.6. The outline serves its purpose (spatial context) even with small jitter. Will be replaced by proper ribbon rendering in Phase 1c.

## Technical Notes

### Draw Order
The spec requires: outline → Lap B → Lap A (bottom to top). This is implemented by:
1. Drawing the outline first with `drawTrackOutline()` 
2. Then Lap B polyline (reference lap)
3. Then Lap A polyline (session lap, on top)

This ensures the outline provides context without obscuring the lap trajectories.

### Color Choice
Spec: `rgba(120, 120, 120, 0.4)` — a mid-grey with 40% opacity. This provides:
- Low visual weight (doesn't compete with lap polylines)
- Spatial context (shows track boundaries)
- Works on the dark background (rgba(0, 0, 0, 0.2))

### Implementation Simplicity
The `drawTrackOutline()` function reuses the same polyline drawing logic as the lap polylines, just with a different stroke style. This keeps the code DRY and makes future refactors (e.g., converting to ribbon rendering in Phase 1a) easier.

## Deferred TODOs

- [ ] Consider making outline color configurable (e.g., for light-mode themes)
- [ ] Phase 1a will replace polylines with ribbons; outline may need to become a filled shape or remain as a centerline reference
- [ ] **Track width research (Phase 6.9):** Investigate official track width data sources and sim racing telemetry standards for accurate track limit rendering. See `track-heatmap-spec.md` Phase 6.9.
- [ ] Jitter fix deferred to Phase 1c ribbon rendering — offset polylines are inherently unstable in high-curvature areas

## Next Phase

Phase 01a (Heatmap Single Lap) can now proceed. The track outline provides spatial context for the heatmap ribbon rendering.

---

**Handoff ready.** All tests pass, learnings documented.
