# Slice 02 — Compute segment bounding box

## Goal

Add a pure-function `computeSegmentBounds(lapA, visibleRange)` that returns the
axis-aligned bounding box of the track coordinates within a visible distance
range. This function is the foundation for auto-zoom — it tells you what part
of the track to zoom into. This slice produces no visual change; it only
exposes the function and validates it with unit tests.

## Context

- `lapA` is an object with `x` (Float64Array, track X in world coords) and
  `z` (Float64Array, track Z in world coords). These are the same arrays
  used by `renderWalkingSkeleton()` and `drawLinkedHighlight()`.
- `visibleRange` (or `currentZoomRange`) is `{ start, end }` where `start`
  and `end` are **lap distance** values (same index space as `lapA.x` /
  `lapA.z`) representing the zoomed segment on the telemetry chart.
- The linked highlight band (`drawLinkedHighlight` in
  `trackHeatmapDrawing.js`) already uses `visibleRange` to find the segment
  index range: it walks `lapA.x` and finds the indices where the distance
  falls between `visibleRange.start` and `visibleRange.end`.
- `computeSegmentBounds` must be a **pure function** — no DOM, no canvas, no
  side effects. It takes data in, returns a bounding box out.

## Steps

1. **Add `computeSegmentBounds(lapA, visibleRange)` to
   `trackHeatmapMap.js`.** Place it after `fitToView` and before
   `renderWalkingSkeleton`. The function:

   - Walks `lapA.x` and `lapA.z` from the first index where
     `lapA.x[i] >= visibleRange.start` to the last index where
     `lapA.x[i] <= visibleRange.end`.
   - Returns `{ minX, maxX, minZ, maxZ }` — the axis-aligned bounding box
     of those points.
   - If `visibleRange` is `null` or `undefined`, returns `null` (no
     auto-zoom needed — the full track is shown).
   - If the range covers the entire lap (start ≤ first point, end ≥ last
     point), returns `null` (full-track range = no auto-zoom needed).
   - If no points fall within the range, returns `null`.
   - Export it so slice 03 can import it.

2. **Write a Node unit test `dev/scripts/test_f16_segment_bounds.js`.**
   The test must use `// @parallel true` and follow the existing unit-test
   pattern (no Playwright — just direct function import and assertion).
   Test cases:

   - **happy path**: synthetic track with 1001 points (same pattern as
     `test_05a_linked_highlight.js`), visible range `{ start: 200, end: 800 }`
     → returns bounds that tightly contain the points from s=200 to s=800.
   - **full-track range**: `{ start: 0, end: 1000 }` on same track → returns
     `null` (no auto-zoom needed).
   - **null range**: pass `null` → returns `null`.
   - **undefined range**: pass `undefined` → returns `null`.
   - **range beyond data**: `{ start: 2000, end: 3000 }` where max distance
     is 1000 → returns `null`.
   - **inverted range**: `{ start: 800, end: 200 }` — the function should
     still return bounds (swap internally or handle gracefully, as the
     caller may pass an inverted range during rapid interaction).

   Each assertion must print `[PASS]` or `[FAIL]` with a descriptive name.

3. **Run `bash scripts/test-summary.sh`.** Must pass with the new test
   included.

4. **Run `npm run build`.** Must succeed (the new export is picked up by
   esbuild).

5. **Commit.**

## Acceptance

- `computeSegmentBounds` is exported from `trackHeatmapMap.js`.
- It is a pure function (no DOM, no canvas, no side effects).
- Returns `{ minX, maxX, minZ, maxZ }` for a valid range, `null` for
  full-track/null/undefined/empty/out-of-range.
- `test_f16_segment_bounds.js` passes with ≥ 6 assertions.
- Full suite passes: `ALL PASS`.
- Build succeeds: `npm run build`.

## Non-goals

- Do not wire `computeSegmentBounds` into the controller (that's slice 03).
- Do not change `fitToView`, `applyUserTransform`, or `mapInteraction.js`.
- Do not add any feature-flag logic or visual behaviour.