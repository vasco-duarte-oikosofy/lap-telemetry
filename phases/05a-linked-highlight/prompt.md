# Phase 05a — Linked Highlight Band from Trace Charts

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 5a from `track-heatmap-spec.md`

**What to do:**
1. Read `track-heatmap-spec.md` section "Phase 5a — Linked highlight band from trace charts"
2. Read `phases/04-hover/handoff.md` to understand the current state
3. Implement a translucent highlight band on the canvas map that mirrors the visible window of the trace charts
4. Write tests first (following `TESTING_LESSONS.md`)
5. Follow XP working agreements in `AGENTS.md`

**Key requirements:**
- Feature flag: `features.mapLinkedHighlight` (default OFF)
- The trace charts already maintain `currentZoomRange = { start, end }` (meters). This is the `visibleRange` prop from the spec. It lives in `main.js` and is updated by `cursor.js` when the user zooms on the charts.
- Pass `currentZoomRange` through `renderTrackHeatmapMap()` to `renderWalkingSkeleton()` as `visibleRange`.
- In `renderWalkingSkeleton`, after all ribbons are drawn, if `showLinkedHighlight` is true and `visibleRange` is provided:
  1. Compute start/end indices: `startIdx = Math.max(0, Math.floor(visibleRange.start))`, `endIdx = Math.min(lapA.x.length - 1, Math.ceil(visibleRange.end))`.
  2. Build a centerline path from `lapA.x[startIdx..endIdx]` mapped through the transform.
  3. Save canvas state, set `ctx.globalCompositeOperation = 'lighten'`.
  4. Stroke the path with `ctx.strokeStyle = 'rgba(255,255,255,0.18)'` and `ctx.lineWidth = ribbonWidthPx + 10`.
  5. Restore `globalCompositeOperation` to `'source-over'`.
  6. Draw two crisp 1px white perpendicular ticks at `startIdx` and `endIdx`. Each tick is perpendicular to the local tangent at that point. Total tick length = `ribbonWidthPx + ribbonGapPx + 12` (halfSpan = `ribbonWidthPx/2 + ribbonGapPx/2 + 6`).
- **Do not dim the unhighlighted portion.** The rest of the lap stays at full saturation. The highlight brightens only the band.
- When `visibleRange` is absent or covers the full lap (`start === 0 && end === maxDist`), the highlight should be a no-op (no visible change from Phase 4).
- The highlight must work correctly under zoom/pan: the same `sStart/sEnd` in track space always highlights the same physical stretch of lap, regardless of current zoom level or canvas size.

**Architecture notes:**
- `renderTrackHeatmapMap()` in `main.js` already receives `lapA`, `lapB`, and `opts`. Add `currentZoomRange` to the opts object (e.g., `visibleRange: currentZoomRange`).
- The existing SVG circuit map already draws a zoom arc via `updateZoomArc()` using `currentZoomRange`. The canvas highlight is the same concept for the new renderer.
- The resampled arrays `lapA.x` / `lapA.z` are indexed by distance in meters (0..maxDist), so `visibleRange.start/end` map directly to array indices (with clamping).
- Keep the highlight drawing inside `trackHeatmapMap.js` — either inline after the ribbon drawing or as a small helper function in the same file. Do not create a new module unless the file exceeds the 200-line soft ceiling.
- You may need to export `getLastTransform` / `setLastTransform` from `trackHeatmapMap.js` if the highlight helper needs the current transform for tick geometry. They are already exported.

**Readout DOM interaction:**
- The hover readout from Phase 4 and the highlight band from Phase 5a are independent features. When both are enabled, both draw on the same canvas. There is no z-order conflict: the highlight is a `lighten` composite, the hover tick is a direct white stroke. They can coexist.

**Acceptance criteria (from spec):**
- Event-loop test: after setting `visibleRange` and re-rendering, the next paint completes within 100ms.
- Render test: with `visibleRange = { start: 400, end: 800 }`, the highlight band's geometric start and end correspond to those `s` values on Lap A's centerline (verified by intersecting the start tick with a known sample position).
- Pixel test: a pixel inside the highlight band at a known throttle-zone position is still in the throttle-green half of the ramp (the composite brightens, does not desaturate).
- Render test: with no `visibleRange` prop, the map renders identically to Phase 4 (pixel-diff baseline).
- Resize test: resizing the window does not change the highlight's `s` boundaries. Track-space, not screen-space.

**Out of scope:**
- Auto-pan to highlight (Phase 6.7)
- Two-way binding / click-to-scrub (Phase 5b)
- Delta coloring inside the highlight band
- Sector boundaries

**When done:**
- `npm test` passes (all existing tests + new Phase 05a tests)
- `phases/05a-linked-highlight/learnings.md` exists
- `phases/05a-linked-highlight/handoff.md` exists
- Commits on `main`, with `refactor:` prefix where appropriate
- Update `phases/PLAN` to mark 05a as DONE
- Update `phases/CURRENT` to the next phase

**Stop at green.** When acceptance passes, commit and stop. Don't start Phase 5b.
