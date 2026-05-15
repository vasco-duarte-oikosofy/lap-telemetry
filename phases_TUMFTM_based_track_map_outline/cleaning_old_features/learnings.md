# Learnings — Cleaning Old Features Replaced by TUMFTM Static Outline

## Removal of mapTrackOutline and learnedTrackOutline

1. **The `anyMapFeature` guard was always true** because of `|| true` added in Phase 02 to account for the unconditional static outline. After removing `mapTrackOutline` and `learnedTrackOutline` from the guard, we replaced it with an explicit comment explaining the `|| true` is justified because the static outline always makes the canvas the preferred renderer. This avoids a misleading list of flags that looks like it drives the canvas-vs-SVG switch.

2. **`learnedBoundariesByLayout` was threaded through many modules**: appState → main (import + pass-through to debugHooks + getMapState) → trackHeatmapController (import + buildOpts) → trackHeatmapMap (option), and ui.js (file loading + boundary detection). Removing it required touching 7 files. The `findBoundaryData` function in `learnedOutline.js` also required a `boundaryKey` helper, and `isBoundaryData` was used in `ui.js` for file-type detection. All of this was a self-contained pipeline that could be cleanly severed.

3. **The `store` import in trackHeatmapController became unused** after removing the learned-boundaries resolution loop that iterated over `store` entries looking for track/layout metadata. Removing the import keeps the module clean.

4. **`drawTrackOutline` and `drawOffsetPolyline` in `trackHeatmapDrawing.js` were self-contained** — `drawTrackOutline` was the only caller of `drawOffsetPolyline`, and no other code imported either. Safe to remove both. The remaining exports (`drawPolyline`, `drawHoverTick`, etc.) are still used by the canvas renderer.

5. **Apex features have zero dependency on removed outline code**. Apex modules (`apexAnnotations.js`, `apexMetrics.js`, `apexMetricsUi.js`) and their tests do not import from `learnedOutline.js` or reference `learnedBoundariesByLayout`. The apex pipeline reads `raw_lap_distance_m`, `path_lateral_m`, `track_edge_m` columns directly from the parquet data — these are telemetry columns, not outline rendering code. The TUMFTM static outline does not change the parquet schema.

## Canvas cursor dot

6. **The SVG cursor dot silently disappears when the canvas renderer is active**. The SVG is set to `display: none` when the canvas takes over, and `#cursor-dot` is a child of the SVG. The canvas needed its own cursor dot mechanism.

7. **Incremental overlay is preferred over full re-render for cursor movement**. Re-rendering the entire canvas on every `mousemove` would be expensive (re-draws all polylines, outlines, heatmaps). Instead, `drawCanvasCursorDot()` saves a small patch of the canvas before drawing the dot, and restores that patch before drawing the next one. This avoids ghost dots without the cost of a full re-render.

8. **The cursor dot must survive full canvas re-renders** (resize, zoom, etc.). The controller stores `_currentCursorBinIdx` and passes it via `buildOpts()` → `renderWalkingSkeleton()`, which draws the dot as part of the full render pass. This ensures the dot reappears after a canvas resize or zoom re-render.

9. **`window.__debugGetCursorBinIdx`** is exposed for Playwright testing, following the established `window.__debug*` pattern in `TESTING_LESSONS.md` (L5).

## Apex adaptation needed (not deletion)

10. **Apex features need adaptation, not deletion**. They currently use the width-profile pipeline's parquet columns for per-corner analysis. The TUMFTM static outline provides visual boundaries only — it does not produce `raw_lap_distance_m`, `path_lateral_m`, or `track_edge_m` columns. The existing parquet data still works for apex metrics. However, future work should evaluate whether TUMFTM-derived corner/turn definitions could supplement or replace the current width-profile-based boundary detection for apex positioning.