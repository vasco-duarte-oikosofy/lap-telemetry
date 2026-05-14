# Phase 01c — Learnings

## What surprised me

- The `trackHeatmapMap.js` file was already at **403 lines** before this subphase started — only 34 lines under the hard ceiling. Adding even a modest dual-ribbon renderer (~45 lines) would have breached the 437-line limit. I had to split the file into `ribbon.js` (79 lines) before I could safely add the new behavior. This validates the spec's hard ceiling rule: without it, the file would have silently grown into an unmaintainable monolith.

- Extracting the ribbon logic into its own module (`ribbon.js`) made the dual-ribbon implementation trivial. The shared `drawRibbonSegment` private helper is reused by both `drawRibbon` and `drawDualRibbons`, keeping the new code to just 20 lines.

- The synthetic test for dual ribbons is very clean: Lap A on a horizontal line with brake→throttle, Lap B with throttle→brake. Sampling above and below the centerline immediately proves independent coloring and correct geometry. No real session data needed.

## What the next agent needs to know

- The dual-ribbon uses **Lap A's centerline as the shared geometric path** for both ribbons. Lap B's colors come from its own resampled `throttle_norm`/`brake_norm` arrays at the same distance index. This works because both laps are resampled to the same `maxDist` grid in `renderAll()`.

- `netAt(lap, index)` safely returns `0` when `throttle` or `brake` arrays are missing (e.g. deltabest CSV with no telemetry). This means dual ribbons gracefully degrade to neutral grey for data-poor laps.

- The offset math is:
  - `offsetA = -(widthPx + gapPx) / 2`  (inside/left)
  - `offsetB = +(widthPx + gapPx) / 2`  (outside/right)
  - Each ribbon spans `[offset ± halfWidth]` in screen space.
  - With default `width=8, gap=2`, the gap is a clean 2px at all zoom levels.

- Feature flag `mapDualRibbon` is wired into the same re-render path as the other map flags in `debugHooks.js` and `main.js`.

## Deferred TODOs

- The `drawTrackOutline` function still uses hardcoded magenta/cyan TEMP colors. That was supposed to be fixed in Phase 00.6 but wasn't. The outline feature works but doesn't match the spec color `rgba(120,120,120,0.4)`. Out of scope for 01c; revisit when outline is next touched.
