# Phase 02 — Zoom and Pan

**Your task:** Implement Phase 2 from `track-heatmap-spec.md`

**What to do:**
1. Read `track-heatmap-spec.md` section "Phase 2 — Zoom and pan"
2. Read `phases/01c-dual-ribbon/handoff.md` to understand the current state
3. Implement zoom/pan interaction for the canvas map
4. Write tests first (following `TESTING_LESSONS.md`)
5. Follow XP working agreements in `AGENTS.md`

**Key requirements:**
- Maintain transform state `{ scale, tx, ty }` (prefer a ref + manual redraw for perf)
- **Wheel to zoom:** zoom centered on the cursor. Clamp `scale` to `[1, 40]`. Use multiplier `1.0015 ** -deltaY`
- **Drag to pan:** pointer down + move updates `tx, ty`. Use Pointer Events (not Mouse Events). Set `cursor: grab`/`grabbing` on `#track-heatmap-canvas`
- **Double-click to reset** to the fit-to-view transform
- Redraw on every transform change
- Ribbon width in **screen pixels** stays constant under zoom: divide the world-space half-width by `scale` when extruding, or extrude in screen space after projecting the centerline
- Add a small zoom indicator in a corner: `1.0× … 40×`. No buttons yet.
- Feature flag: `features.mapZoomPan` (default OFF)

**Architecture notes:**

The current `fitToView()` returns an object with `toScreenX()`, `toScreenY()`, `scale`, `offsetX`, `offsetY`. It maps world directly to screen with no user zoom/pan. The Phase 2 transform must compose with `{ scale, tx, ty }`:

```js
// Fit-to-view computes a base scale S and offset (ox, oy)
// User transform adds scale multiplier m and pan (tx, ty)
// Effective: sx = ox + (x - bx) * S * m + tx
//            sy = oy + (bz - z) * S * m + ty
```

The simplest thing that could possibly work:
1. Store `{ mScale: 1, panX: 0, panY: 0 }` on the canvas element or in a module-level ref in `trackHeatmapMap.js`
2. Compute the fit-to-view transform as today, then multiply by `mScale` and add pan offset
3. Pass the composited transform into all draw helpers instead of the raw `fitToView` result
4. On wheel, update `mScale` and pan so zoom is centered on cursor
5. On pointer drag, update `panX/panY`
6. On double-click, reset to `{ mScale: 1, panX: 0, panY: 0 }` and re-fit

**Ribbon width constancy:**
The `drawRibbon` function currently extrudes in **screen space** after calling `transform.toScreenX/toScreenY`, then offsets by `offsetPx`. Since `offsetPx` is already in screen pixels, ribbon width does NOT scale with zoom automatically — this is correct. The spec asks for "screen pixels stays constant:" the existing implementation already satisfies this. Verify with a render test at scale=1, 10, 40.

**Acceptance criteria (from spec):**
- Interaction test (Playwright): wheel events change `scale` within `[1, 40]`; pointer-drag changes `tx`/`ty` 1:1 with movement; double-click resets to fit-to-view exactly
- Render test: at scale=1, 10, 40, ribbon thickness in screen pixels is constant at known sample positions (assert ±0.5px)
- Perf test: scripted pan across the lap for 2 seconds at 60Hz; no frame exceeds 16ms p99. If this fails and Phase 1c didn't, it's a transform bug, not a rendering bug

**Out of scope:**
- Zoom buttons (Phase 6.5)
- Keyboard shortcuts (Phase 6.4)
- Minimap (Phase 6.6)
- Highlight band (Phase 5a)
- Hover readout (Phase 4)
- Legend (Phase 3)

**When done:**
- `npm test` passes (all existing tests + new Phase 02 tests)
- `phases/02-zoom-pan/learnings.md` exists
- `phases/02-zoom-pan/handoff.md` exists
- Commits directly on `main`, with `refactor:` prefix where appropriate
- Update `phases/PLAN` to mark 02 as DONE
- Update `phases/CURRENT` to the next phase

**Stop at green.** When acceptance passes, commit and stop. Don't start Phase 3.

---

## Implementation Notes

### Transform composition
The existing code does:
```js
const transform = fitToView(boundsA, boundsB, w, h, padding);
drawPolyline(ctx, lapA.x, lapA.z, transform, color);
```

`fitToView` returns `{ scale, offsetX, offsetY, toScreenX, toScreenY }`. For Phase 2, you have two options:

**Option A: compose inside `fitToView`**
Add an `applyUserTransform(base, zoomPan)` that returns a new transform object with composed functions. Keeps draw helpers untouched. Good separation.

**Option B: store zoom state globally and let `fitToView` read it**
Less clean. Prefer Option A.

### Pointer events vs Mouse events
The trace charts already use mouse events for drag-to-zoom (different gesture). The map canvas is a separate DOM element (`#track-heatmap-canvas`), so there's no conflict. Use `pointerdown`/`pointermove`/`pointerup` directly on the canvas. Remember to `setPointerCapture` on the canvas in the `pointerdown` handler so dragging outside the element still works.

### Zoom clamping
```js
const oldScale = state.scale;
const newScale = Math.min(40, Math.max(1, oldScale * Math.pow(1.0015, -deltaY)));
const zoomRatio = newScale / oldScale;
// Center zoom on cursor:
state.panX += mx * (1 - zoomRatio);
state.panY += my * (1 - zoomRatio);
state.scale = newScale;
```

### Double-click detection
The trace charts handle dblclick for zoom reset. The canvas also needs it. The DOM event `dblclick` fires automatically — just add a listener on `#track-heatmap-canvas`.

### Zoom indicator
Add a small absolutely-positioned `<span>` inside `#circuit-map-panel` (like the map legend that's already there). Only visible when `mapZoomPan` is on. Update text on every render.

### File size watch
`trackHeatmapMap.js` is currently ~330 lines after the ribbon extraction. It can grow modestly, but if zoom/pan logic exceeds ~100 lines, consider extracting `mapInteraction.js` as a separate module.
