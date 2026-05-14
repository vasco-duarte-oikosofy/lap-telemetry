# Phase 03 — Lap Legend and Identification

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 3 from `track-heatmap-spec.md`

**What to do:**
1. Read `track-heatmap-spec.md` section "Phase 3 — Lap legend and identification"
2. Read `phases/02-zoom-pan/handoff.md` to understand the current state
3. Implement lap legend (swatches + labels), ribbon outer-edge outlines, and color-ramp legend on the canvas map
4. Write tests first (following `TESTING_LESSONS.md`)
5. Follow XP working agreements in `AGENTS.md`

**Key requirements:**
- Feature flag: `features.mapLegend` (default OFF)
- **Lap legend (top-left):** absolute-positioned overlay inside `#circuit-map-panel` showing:
  - Lap A: small swatch in `lapA.color` + label (e.g. "Session")
  - Lap B: small swatch in `lapB.color` + label (e.g. "Reference")
- **Ribbon outer-edge outline:** 1px stroke along the **outer edge** of each ribbon in that lap's accent color, drawn full-lap. Inner edges are not outlined. Draw this after the ribbon fill so it sits on top.
- **Color-ramp legend (top-right):** a horizontal gradient strip `dark blue (#0a3d91) → neutral (#2a3340) → dark green (#0f7a2e)` with labels "Brake" and "Throttle" at the ends. About 160×16 px. Use the actual `colorForNet` ramp to generate the gradient stops — do not hardcode a CSS `linear-gradient` string that won't match the OKLCh interpolation.
- The lap legend and color-ramp legend should only be visible when `features.mapLegend` is enabled.
- Legends must not interfere with zoom/pan interaction (pointer events should pass through; use `pointer-events: none` on the legend overlays).

**Architecture notes:**

The existing renderer in `trackHeatmapMap.js` currently draws:
1. Background fill
2. Track outline (if enabled)
3. Heatmap ribbons (single or dual)
4. Start/finish marker

For Phase 3, you have two options for drawing the ribbon outlines:

**Option A: draw outline strokes in `ribbon.js`**
Extend `drawRibbon` or `drawDualRibbons` to optionally draw an additional 1px stroke on the outer edge of each ribbon using the lap accent color. This keeps all ribbon logic in one place. The outer edge is the side farther from the centerline (positive offset side for Lap B, negative offset side for Lap A).

**Option B: draw outlines in `trackHeatmapMap.js` after calling drawDualRibbons**
Less clean — the outline needs to know the same normals and offsets. Prefer Option A.

**Legend placement:**
Use absolutely-positioned `<div>` elements inside `#circuit-map-panel` (which already has `position: relative`). Do not render them on the canvas — HTML overlays are higher-fidelity for text and easier to style responsively.

**Color-ramp legend:**
The simplest reliable approach: create a `<canvas>` element (e.g. 160×16) in JS, draw the gradient by sampling `colorForNet` at each pixel column, then use `canvas.toDataURL()` as a background image for a `<div>`. This guarantees the rendered ramp exactly matches the OKLCh interpolation used for the ribbons.

**Acceptance criteria (from spec):**
- Render test: legend is visible at the top-left with both lap labels and swatches.
- Pixel test: a pixel sampled at the right end of the ramp legend equals `colorForNet(1)` exactly. A pixel sampled at the left end equals `colorForNet(-1)` exactly. A pixel sampled at the middle equals `colorForNet(0)` exactly.
- Render test: each ribbon's outer edge is outlined in its lap accent color. Inner edges are not outlined.
- Interaction test: pan/zoom gestures still work when the legend is visible (pointer events pass through overlays).

**Out of scope:**
- Hover tooltips / readout (Phase 4)
- Statistics or delta numbers in the legend
- Legend repositioning on zoom
- Responsive font-size adjustments below the existing breakpoint

**When done:**
- `npm test` passes (all existing tests + new Phase 03 tests)
- `phases/03-legend/learnings.md` exists
- `phases/03-legend/handoff.md` exists
- Commits on `main`, with `refactor:` prefix where appropriate
- Update `phases/PLAN` to mark 03 as DONE
- Update `phases/CURRENT` to the next phase

**Stop at green.** When acceptance passes, commit and stop. Don't start Phase 4.

---

## Implementation Notes

### Ribbon outer-edge outline
In `drawDualRibbons`, the outer edge of Lap A is at `offsetA - halfWidth` (more negative), and the outer edge of Lap B is at `offsetB + halfWidth` (more positive). After drawing each ribbon segment, draw a 1px line along these two edges using `lapA.color` and `lapB.color`.

For the single-lap `drawHeatmapRibbon`, the outer edges are at `0 - halfWidth` and `0 + halfWidth` — but the spec only asks for outer-edge outline in dual-ribbon mode. Focus on `drawDualRibbons` for this feature; single-lap can be a no-op or follow the same pattern if trivial.

### Lap legend DOM structure
```html
<div id="map-lap-legend" class="map-lap-legend" style="display:none;">
  <div class="legend-row">
    <span class="legend-swatch" style="background: var(--session)"></span>
    <span class="legend-label">Session</span>
  </div>
  <div class="legend-row">
    <span class="legend-swatch" style="background: var(--ref)"></span>
    <span class="legend-label">Reference</span>
  </div>
</div>
```
Insert this into `#circuit-map-panel` on first render when `mapLegend` is enabled.

### Color-ramp legend DOM structure
```html
<div id="map-ramp-legend" class="map-ramp-legend" style="display:none;">
  <span class="ramp-label">Brake</span>
  <canvas class="ramp-bar" width="160" height="16"></canvas>
  <span class="ramp-label">Throttle</span>
</div>
```

### Feature flag wiring
- Add `mapLegend: false` to `features` in `appState.js`
- Add to `KNOWN_FLAGS` in `scripts/test_feature_flag_dropdown.js`
- Wire `window.__setFeatureFlag` in `debugHooks.js` to trigger `renderTrackHeatmapMap()`
- Update `anyMapFeature` guard in `main.js` to include `mapLegend`

### File size watch
`trackHeatmapMap.js` is ~350 lines. Legend DOM creation can go in a small helper in `trackHeatmapMap.js` or a new `mapLegend.js`. If it exceeds ~100 lines of logic, extract it. One file, one job.
