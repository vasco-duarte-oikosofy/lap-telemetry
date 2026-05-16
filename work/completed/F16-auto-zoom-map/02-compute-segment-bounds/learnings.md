# Slice 02 Learnings — Compute segment bounds

## What surprised me

1. **ES module testing via esbuild bundle**: `trackHeatmapMap.js` is an ES module with many side-effect imports (canvas, DOM, etc.) that can't run in Node directly. The cleanest way to test `computeSegmentBounds` (a pure function with zero imports) was to use esbuild to bundle it into a temporary CommonJS file, marking all the other imports as `--external`. This pattern works well for testing isolated pure functions from ES modules without Playwright.

2. **Full-track detection**: The spec says `visibleRange` covering the entire lap should return `null`. The detection is `start <= firstPoint && end >= lastPoint`. This means a range like `{ start: -10, end: 2000 }` on a 0–1000 lap also returns `null`, which is correct — it's effectively "show everything."

3. **Inverted range handling**: During rapid chart zoom interaction, the user might produce an inverted range where `start > end`. Rather than returning `null` and failing silently, the function normalizes by swapping start/end. This matches the spirit of the existing `drawLinkedHighlight` which uses `Math.floor`/`Math.ceil` — it's robust to imprecise input.

4. **`lapA.x` doubles as distance AND x-coordinate**: In the current codebase, `lapA.x[i]` serves as both the track X coordinate and the distance along the track. The `visibleRange.start/end` values are distances, so `lapA.x[i]` is the right array to search. This is not a naming collision — it's how the data model works.