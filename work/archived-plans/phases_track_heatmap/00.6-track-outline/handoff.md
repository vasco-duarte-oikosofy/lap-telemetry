# Phase 00.6 — Track Outline Background (Handoff)

## Summary

**Status:** ✅ COMPLETE  
**Feature flag:** `features.mapTrackOutline` (default: OFF)  
**Development base:** `main`

## What Changed

### New Files
None (feature implemented in existing files)

### Modified Files

1. **`web/js/trackHeatmapMap.js`** (167 lines, was 140 lines)
   - Added `drawTrackOutline(ctx, trackX, trackZ, transform)` function
   - Modified `renderWalkingSkeleton()` to accept `options` parameter with `showOutline` flag
   - Draw order: outline first (if enabled), then Lap B, then Lap A

2. **`web/js/main.js`** (514 lines, was 511 lines)
   - Modified `renderTrackHeatmapMap()` to pass `{ showOutline: features.mapTrackOutline }` option

3. **`web/js/appState.js`** (73 lines, was 71 lines)
   - Added `mapTrackOutline: false` to `features` object

4. **`scripts/test_006_track_outline.js`** (new, 456 lines)
   - Test suite for track outline feature
   - Verifies outline renders, color matches spec, draw order is correct

## Technical Approach

### Feature Flag Pattern
The track outline is controlled by `features.mapTrackOutline`, default OFF. This allows the feature to be developed and tested incrementally without affecting the walking skeleton (Phase 00.5) which remains functional.

### Draw Order
The spec requires drawing in this order:
1. Track outline (bottom layer) — `rgba(120, 120, 120, 0.4)`
2. Lap B polyline (reference) — orange `#ff9800`
3. Lap A polyline (session, top) — light blue `#4fc3f7`

This is implemented in `renderWalkingSkeleton()` by calling `drawTrackOutline()` before the lap polylines when `showOutline` is true.

### Outline Geometry
The outline is derived from Lap A's `(x, z)` track coordinates (per spec: "derived from either lap — they should be nearly identical"). The same `transform` is used to project world coordinates to screen space.

## Test Results

All 9 assertions pass:
- **Scenario 1:** Canvas renders with content (4/4 passed)
- **Scenario 2:** Outline color matches spec (2/2 passed)
- **Scenario 3:** Draw order correct (2/2 passed)
- **Scenario 4:** Visual smoke test (screenshot artifact)
- **Scenario 5:** No console errors (1/1 passed)

### Existing Tests
Phase 00.5 walking skeleton tests still pass (12/12), confirming no regression.

## Acceptance Criteria Met

✅ **Render test:** Track outline is visible underneath the lap polylines  
✅ **Render test:** Outline has lower visual weight (lower contrast via alpha=0.4)  
✅ **Pixel test:** Outline color matches spec (grey ~120,120,120 with alpha)

## Known Limitations

1. **No feature flag toggle UI.** The outline can only be enabled via `window.__setFeatureFlag('mapTrackOutline', true)` in the browser console. This is intentional — feature flags are dev-only until acceptance.

2. **Outline uses Lap A's track only.** If Lap A and Lap B have significantly different racing lines, the outline may not perfectly match Lap B's trajectory. This is acceptable per spec ("derived from either lap — they should be nearly identical").

3. **Outline is a polyline, not a ribbon.** Phase 1a will upgrade to ribbon rendering; the outline may need to be reconsidered then (e.g., as a filled track surface vs. centerline).

4. **Jitter in high-curvature corners.** The offset polyline algorithm produces minor artifacts in tight corners (Eau Rouge, La Source hairpin). This is a known limitation of tangent-based offset calculations. The proper fix requires ribbon rendering with quads (Phase 1c). For now, the outline serves its purpose (spatial context) despite small visual artifacts.

## Integration with Phase 00.5

The walking skeleton (Phase 00.5) remains the foundation. The track outline is an optional enhancement:
- When `mapTrackOutline` is OFF: walking skeleton renders as before (polylines only)
- When `mapTrackOutline` is ON: outline draws underneath polylines

Both feature flags can be toggled independently via `window.__setFeatureFlag()`.

## Next Steps

Phase 01a (Heatmap Single Lap) can now proceed. The track outline provides spatial context for understanding where the heatmap ribbon deviates from the track centerline.

## Deferred TODOs

- [ ] Consider outline styling options (color, width) for future customization
- [ ] Phase 1a: evaluate if outline should remain a polyline or become a filled track surface
- [ ] Consider adding outline to the legend (Phase 03)
- [ ] **Track width research (Phase 6.9):** See `track-heatmap-spec.md` — investigate official track width data sources for accurate track limit rendering
- [ ] Jitter fix deferred to Phase 1c ribbon rendering — offset polylines are inherently unstable in high-curvature areas

## Commit History

```
feat: add track outline background (Phase 00.6)
- Add drawTrackOutline() to trackHeatmapMap.js
- Modify renderWalkingSkeleton() to accept showOutline option
- Wire up features.mapTrackOutline flag in appState.js
- Pass showOutline from main.js renderTrackHeatmapMap()
- Draw order: outline → Lap B → Lap A (bottom to top)
- Outline color: rgba(120, 120, 120, 0.4) per spec

test: add Phase 00.6 track outline test suite
- Verify outline renders underneath polylines
- Verify outline color matches spec (grey, low contrast)
- Verify draw order (outline first, then laps)
- Visual smoke test with real fixture data
```

## Verification

To verify the changes work:
1. Open `dist/compare.html` in a browser
2. Load a session file and compare two laps
3. In browser console, run: `window.__setFeatureFlag('mapTrackOutline', true)`
4. Click "Compare" button again
5. Observe: Faint grey track outline visible underneath both lap polylines

---

**Handoff complete.** Phase 00.6 is done. The track outline provides spatial context for the heatmap ribbon rendering in Phase 01a.
