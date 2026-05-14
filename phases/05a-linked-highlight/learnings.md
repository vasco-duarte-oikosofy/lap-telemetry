# Phase 05a — Learnings

## What surprised me

1. **Canvas anti-aliasing makes 1px ticks hard to test for pure white.** The spec asks for "crisp 1px white perpendicular ticks," but on a horizontal track rendered at non-integer screen Y, the tick endpoints anti-alias and never hit `(255,255,255)`. The brightest pixels we saw were `(213,213,213)`. We had to relax the test threshold to `r+g+b > 400` and accept ±1px position tolerance.

2. **Floating-point in `fitToView` can shift a tick by one pixel.** `470/1000*400` in JS evaluates to `202.99999999999997` rather than `203.0`. This pushes the 1px tick slightly left of the expected column, so the resize test must tolerate a 1-pixel drift rather than asserting exact equality.

3. **`globalCompositeOperation = 'lighten'` with `rgba(255,255,255,0.18)` does exactly what the spec wants.** The composite brightens the underlying heatmap without washing out hue. A throttle-green pixel becomes `(46,122,46)` — still green-dominant, just lifted. We verified this with a synthetic pixel test.

4. **The no-op cases are surprisingly important.** Without `visibleRange`, or with a full-lap range (`start=0, end=maxDist`), the highlight must not draw at all. A single missing guard caused 0-pixel diff failures in the baseline comparison test until we added the explicit `startIdx === 0 && endIdx >= maxIdx` early return.

## Anything the next agent needs to know

- The resampled arrays (`currentTrackX`, `currentTrackZ`, etc.) are indexed by distance in meters, so `visibleRange.start/end` map directly to array indices with simple `Math.floor`/`Math.ceil`.
- `drawLinkedHighlight` lives in `trackHeatmapMap.js` and is called after the ribbon drawing but before `setLastTransform()`.
- The feature flag is `features.mapLinkedHighlight` (default OFF). It is wired into `debugHooks.js` so toggling it via the console dropdown re-renders the map.
- Tests use a `halfSpan = ribbonWidthPx/2 + ribbonGapPx/2 + 6` tick length and expect the tick to be perpendicular to the local tangent in **screen space** (computed from neighboring transformed points).
