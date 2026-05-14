# Phase 04 — Hover Crosshair and Per-Lap Readout

> **Branching convention:** WE DEVELOP ON `main`. Do not create a branch named `phase/04-hover`. Write commits directly to `main`. Phase branches are only for reference after the fact.

**Your task:** Implement Phase 4 from `track-heatmap-spec.md`

**What to do:**
1. Read `track-heatmap-spec.md` section "Phase 4 — Hover crosshair and per-lap readout"
2. Read `phases/03-legend/handoff.md` to understand the current state
3. Implement hover crosshair (white perpendicular tick across both ribbons) and a per-lap readout panel near the cursor
4. Write tests first (following `TESTING_LESSONS.md`)
5. Follow XP working agreements in `AGENTS.md`

**Key requirements:**
- Feature flag: `features.mapHover` (default OFF)
- On `pointermove` over the canvas (when NOT dragging), compute the nearest point on **Lap A's centerline** in world space. Use a precomputed spatial index — a uniform grid keyed by world coords is plenty; quadtree is overkill.
- From the nearest point, get the corresponding `s` on Lap A. Look up Lap B's matching sample via `sLookup`.
- Draw a short white perpendicular tick across **both** ribbons at the matched location. Style: same as start/finish tick but 1px wide, 10px long (5px each side of centerline), white. Only drawn when `mapHover` is enabled.
- Render a small readout panel near the cursor (offset 12px right and 12px down). It must flip to stay on-screen when near canvas edges.
  - Top row: `Distance: 1432 m` (monospace, subtle color)
  - Two rows below: `Lap A — Throttle 87% / Brake 0%` and `Lap B — Throttle 62% / Brake 12%`
  - Lap labels rendered in that lap's accent color; throttle numbers in full-saturation green, brake numbers in full-saturation blue
- Hide the readout when the pointer leaves the canvas.
- Coalesce pointermove updates with `requestAnimationFrame` — do not re-query the spatial index or re-render the DOM more than once per animation frame.
- During a pointer-drag (pan), the readout and tick must be hidden. They reappear on the next `pointermove` after drag ends.

**Architecture notes:**

The existing interaction in `mapInteraction.js` already handles:
- `pointerdown` → starts drag, captures pointer, sets `cursor: grabbing`
- `pointermove` → updates pan offset if dragging
- `pointerup` → ends drag, releases capture, sets `cursor: grab`

For Phase 4, extend `mapInteraction.js` (or create a `mapHover.js` helper) to:
1. Track whether we're currently dragging (the interaction layer already knows this).
2. On `pointermove` when NOT dragging, compute nearest point on Lap A centerline, look up `s` and matching Lap B sample, update hover state.
3. Trigger a re-render of the canvas + readout. The canvas re-render should draw the tick; the readout is a separate DOM element.

**Spatial index approach:**
- Build a uniform grid once per render (when track data changes), keyed by world `(x, z)` coords.
- Cell size ≈ 20m. For each centerline point, insert into the cell it falls in.
- Query: convert cursor world coords to cell, search that cell + 8 neighbors, brute-force nearest within those cells.
- The grid can be built inside `trackHeatmapMap.js` and passed to the hover helper, or the hover helper can receive `lapA` and `transform` and build it lazily.

**Readout DOM structure:**
```html
<div id="map-hover-readout" class="map-hover-readout" style="display:none;">
  <div class="readout-dist">Distance: 1432 m</div>
  <div class="readout-row" style="color: var(--session)">Lap A — Throttle 87% / Brake 0%</div>
  <div class="readout-row" style="color: var(--ref)">Lap B — Throttle 62% / Brake 12%</div>
</div>
```
Insert this into `#circuit-map-panel` on first render when `mapHover` is enabled. Position absolutely using `left/top` in CSS pixels.

**Canvas tick drawing:**
- In `renderWalkingSkeleton`, after all ribbons are drawn, if `showHover` is true and hover state has a valid `s`, draw the tick.
- The tick is a 1px white line perpendicular to the local tangent at the matched point, spanning both ribbons (length = ribbonWidth + gap + 4px overshoot on each side).
- Use `drawStartFinishTick` style but thinner (1px) and longer.

**Feature flag wiring:**
- Add `mapHover: false` to `features` in `appState.js`
- Add to `KNOWN_FLAGS` in `scripts/test_feature_flag_dropdown.js`
- Wire `window.__setFeatureFlag` in `debugHooks.js` to trigger `renderTrackHeatmapMap()`
- Update `anyMapFeature` guard in `main.js` to include `mapHover`

**Acceptance criteria (from spec):**
- Interaction test: pointer-move over a known position on the canvas produces a readout with the expected `s`, throttle, brake values (assert against fixture data).
- Render test: the perpendicular tick is geometrically perpendicular to the local racing line (compute the tangent at the sample and assert dot-product with the tick direction is within epsilon of zero).
- Interaction test: during a pointer-drag (pan), the readout is hidden.
- Render test: the readout flips horizontally/vertically near canvas edges to stay on-screen.

**Out of scope:**
- Click-to-pin or multi-point comparison
- Spatial index persistence across renders (rebuild on each render is fine for now)
- Highlight band (Phase 5a)
- Statistics or delta numbers beyond throttle/brake

**When done:**
- `npm test` passes (all existing tests + new Phase 04 tests)
- `phases/04-hover/learnings.md` exists
- `phases/04-hover/handoff.md` exists
- Commits on `main`, with `refactor:` prefix where appropriate
- Update `phases/PLAN` to mark 04 as DONE
- Update `phases/CURRENT` to the next phase

**Stop at green.** When acceptance passes, commit and stop. Don't start Phase 5a.
