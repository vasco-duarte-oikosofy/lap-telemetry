# Phase 03 — Learnings

## What surprised me

1. **Outer-edge outline arithmetic is inverted in `drawRibbonSegment`.** The function names its edge offsets `inner = offsetPx - halfWidth` and `outer = offsetPx + halfWidth`, but for Lap A (negative offset), `inner` is actually the side farther from the centerline — the true outer edge. I had to carefully trace the sign conventions before adding strokes in `drawDualRibbons`.

2. **Using a 161px-wide ramp canvas makes the "exact middle" pixel test deterministic.** With an even width (160), there is no single integer column at net=0. Switching to 161 columns so x=80 maps to net=0 made the acceptance pixel test exact without tolerance gymnastics.

3. **Pointer events pass-through is already solved by CSS.** Setting `pointer-events: none` on absolutely-positioned overlays is sufficient; no canvas interaction code needed changes. Playwright verified this by wheel-zooming through the legend.

4. **Creating DOM elements inside `renderWalkingSkeleton` on every frame is bad, but creating once and toggling `display` is fine.** The `updateMapLegend` helper checks for existing elements before creating, keeping the render loop frame-budget-neutral after the first call.

## Deferred TODOs

- Hover tooltips / readout (Phase 4)
- Statistics or delta numbers in the legend
- Legend repositioning on zoom (currently fixed)
- Responsive font-size adjustments below the existing breakpoint
