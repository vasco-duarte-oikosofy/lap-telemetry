# Spec: Side-by-Side Track Heatmap with Linked Zoom/Pan

**Audience:** implementing agent (frontend, telemetry app for simracers).
**Goal:** Render two laps side by side on the same track map, with a Brake↔Throttle color heatmap painted along each lap's racing line, supporting zoom, pan, and a highlight band that mirrors the visible window of the trace charts.
**Method:** ship in small **subphases**. Each subphase is an **independent delivery** — one subphase, one merge, one acceptance run. We never deliver several subphases at the same time, even when they look small enough to combine. The discipline is the point: a single subphase that fails acceptance is trivially revertible; two bundled subphases require archaeology.

Subphases are independently shippable. Any subphase can be deployed on its own, and a stalled or skipped later subphase never breaks the work that came before it. Do not start a subphase until the previous subphase's acceptance criteria pass. You may stop the project at the end of any subphase and still have a usable improvement live.

---

## XP working agreements (read first, then re-read whenever you're tempted to violate one)

These apply to **every** subphase. They are not negotiable, and they override convenience.

1. **One subphase at a time.** Never bundle two subphases into one delivery, even if they feel related, even if the second is "trivial." If you find yourself writing "and while I was there, I also…" — stop, revert, do the second thing as its own subphase. The point is reversibility, not throughput.

2. **Test-first.** Write the failing test before the code that makes it pass. Acceptance criteria are written as executable tests in this spec; if a criterion is prose-only, your job is to turn it into a test before you implement the feature. "I'll add tests after" means "I won't add tests."

3. **Commit cadence: small and green.** Many commits per subphase, each one passing the existing test suite. If a commit can't be green, it's too big — split it. "WIP" commits do not exist on the main branch.

4. **Refactor commits are separate from behavior commits. Always.** If a change both moves code around *and* changes what the user sees, it is two commits. Refactor first, verify green, then change behavior. This is the single most important rule for keeping the spec's subphases honest. Phrase from Kent Beck: *make the change easy, then make the easy change.*

5. **YAGNI is an active veto.** Do not add abstractions, configuration knobs, generic helpers, or "while I'm here" cleanups that the current subphase does not need. If you find yourself writing a generic `<TrackMap>` when the spec asks for `<TrackHeatmapMap>`, stop. If a third use case appears later, refactor then — not now. *You aren't gonna need it.*

6. **The simplest thing that could possibly work.** Pick the dumbest implementation that satisfies the acceptance test. Optimize only when a later subphase reveals a real problem with the dumb version. A linear scan beats a quadtree until the scan is measurably too slow.

7. **Spike, then stabilize.** When you hit a genuine unknown (e.g. "does this browser support OKLCh interpolation," "does Lap A's `s` parameterization actually match Lap B's on real data"), write a throwaway spike in a scratch file. Learn the answer. **Throw the spike away.** Then implement properly with tests. Do not ship the spike — spikes lack the rigor of real code and are how production bugs get born.

8. **Stop at green.** When the current subphase's acceptance passes, stop. Commit, open a PR, move on. Do not keep polishing into the next subphase's territory — that breaks the "one subphase at a time" rule and pollutes the delivery boundary.

9. **When in doubt, ask. Do not assume.** If the spec or the data is ambiguous, surface the question to the human before implementing. Filling gaps with plausible defaults is the most common way agents ship the wrong thing. Especially flag: real-data shape questions, browser compatibility surprises, and any acceptance criterion you can't turn into a test.

10. **Narrate decisions like you're pairing.** Commit messages and PR descriptions should explain *why*, not just *what*. Write them as if a pair-programmer is reading over your shoulder and will catch any sloppy reasoning. This is how a solo agent gets the benefits of pair programming.

---

## File architecture constraints

Follow the **existing** file architecture and separation already in place in the project. Do not invent new top-level directories or restructure the layout. Match the conventions you find when you read the codebase.

**Hard rules:**
- Files should be small and easy to read for an agent. Default ceiling: **200 lines per file**. Going over 200 lines requires a very good reason, named in the PR description.
- **No file may exceed `main.js`, which stands at 437 lines. This is a hard ceiling.** Not a guideline, not a stretch goal. A hard no. If you are approaching 437 lines in any file, that file needs to be split — full stop, before the subphase merges.
- Files should be **coherent**: one file, one job. A file mixing the color ramp, the renderer, and the hover logic is wrong even if it's 80 lines long.
- Prefer many small modules with explicit exports over one large module with internal sections. Agents read small files faster and refactor them more safely.
- If splitting a file produces two files that obviously want to be in the same folder, put them there. Mirror the existing folder structure.

When in doubt about where a new file belongs, read three nearby files and follow their pattern. Do not introduce a new convention.

---

## 0. Shared definitions (read once, refer back)

### 0.1 Data model

Assume each lap is provided as a time-ordered array of samples:

```ts
type Sample = {
  t: number;          // seconds from lap start
  s: number;          // distance from lap start, meters (monotonic — see below)
  x: number;          // world X (meters) — track centerline-ish position
  y: number;          // world Y (meters)
  throttle: number;   // 0..1
  brake: number;      // 0..1
  // (other channels exist but are out of scope here)
};

type Lap = {
  id: string;
  label: string;      // e.g. "Lap 7 — 1:42.318"
  color: string;      // accent color for UI chrome (not the heatmap)
  samples: Sample[];
};
```

Two laps are passed in: `lapA` (reference) and `lapB` (compared). They may have different lengths and different sample counts. They share the same track geometry — but their `(x, y)` traces will differ slightly because the driver took different lines.

**Invariants the renderer relies on:**
- `t` is strictly monotonic increasing.
- `s` is strictly monotonic increasing within a normal lap. Pit-lane laps may violate this; those are **out of scope** and should be filtered out upstream before the component is mounted.
- `t` and `s` move together (no rewinds in either).

If real data violates these invariants, the data pipeline owner needs to know — surface it as a hard error in dev, not as a silent visual glitch. Acceptance tests in subphase 1b explicitly verify this with debug overlays.

### 0.2 The color ramp (the single most important visual rule)

One channel drives the color: **net pedal input** = `throttle - brake`, range `[-1, +1]`.

- `-1` (full brake, no throttle) → **dark blue** `#0a3d91`
- `0` (coasting, neither) → **neutral mid** `#2a3340` (near-background, low chroma)
- `+1` (full throttle) → **dark green** `#0f7a2e`

Interpolate in OKLCh (or HSL as a fallback) so the ramp stays perceptually smooth and never passes through muddy brown. Brake side ramps **light blue → dark blue** as brake increases. Throttle side ramps **light green → dark green** as throttle increases. Overlap (both pressed, e.g. trail braking) resolves by net value — that is the whole point of using a single signed channel.

Expose the ramp as a function `colorForNet(net: number): string` and a 256-entry LUT for fast lookup. Every later subphase reuses these. **Do not** re-derive the ramp inline.

### 0.3 Lap rendering geometry

Each lap is drawn as a **ribbon**, not a polyline. The ribbon is a thick strip following `(x, y)`, perpendicular-extruded by a constant track-half-width in screen pixels. The ribbon is segmented per sample-pair; each segment is filled with `colorForNet(avg(net_i, net_{i+1}))`. A 1px darker stroke on each side of the ribbon improves legibility against the dark background.

Ribbon width in screen pixels stays **constant under zoom** (the ribbon does not get fatter when you zoom in — the track gets longer, the ribbon stays the same thickness). This matches the reference images.

### 0.4 Side-by-side layout

Lap A and Lap B are drawn as **two parallel ribbons offset from a shared centerline**, not stacked as two separate maps. Offset = `ribbonWidth + gap` (gap ≈ 2px). Lap A is on the inside (left of travel direction), Lap B on the outside, consistently around the whole lap. This matches the third panel of reference image 1, where two ribbons run parallel through every corner.

The shared centerline is computed once from Lap A's `(x, y)` (Lap A is treated as the geometric reference, by convention — not because Lap A is "correct"). Lap B's heatmap is sampled by **distance `s`**, not by index, so the two ribbons stay in spatial sync corner-by-corner even when sample counts differ.

**Known limitation, acknowledged and deferred:** if `|xy_B(s) − xy_A(s)|` exceeds some threshold (~5m), the parallel-ribbon assumption breaks visually (off-track excursion, dramatically different corner cut). Out of scope for now; revisit if it shows up in real data.

### 0.5 Coordinate spaces

- **World space:** meters, from the telemetry. Y-up. This is the source of truth.
- **Track space:** world space rotated/translated so the track fits a canonical bounding box. Computed once at load.
- **Screen space:** pixels in the canvas, after applying the current pan/zoom transform.

All hit-testing, highlight bands, and trace-chart links operate in **track space**, never in screen space. Pan/zoom only changes the world→screen transform.

### 0.6 Tech assumptions

- Rendering: **HTML Canvas 2D** (not SVG). The map has thousands of segments per lap and must stay smooth during pan/zoom. SVG will choke.
- Zoom/pan: implement directly on the canvas with a 3×3 affine transform. Do not pull in a heavy chart library for this.
- Framework-agnostic spec, but assume React + TypeScript unless the agent's project says otherwise.
- Existing trace charts may or may not exist yet; subphase 5a consumes a `visibleRange` prop **if provided** and is a no-op otherwise. Subphases 0–4 do not depend on the trace charts at all.

### 0.7 Feature flags

Every subphase merges to main behind a feature flag, default-off. The flag flips on once acceptance is signed off. Flags are permanent until the subphase is the only path and there's no other path to fall back to.

```
features.mapLayoutPromoted       // Phase 0
features.mapRendererResponsive   // Phase 0.1
features.mapWalkingSkeleton      // Phase 0.5
features.mapHeatmapSingleLap     // Phase 1a
features.mapSAlignment           // Phase 1b (with dev debug overlay)
features.mapDualRibbon           // Phase 1c
features.mapZoomPan              // Phase 2
features.mapLegend               // Phase 3
features.mapHover                // Phase 4
features.mapLinkedHighlight      // Phase 5a
features.mapClickToScrub         // Phase 5b
```

This is the mechanism that makes "independently shippable" real instead of aspirational. Trunk-based development, no long-lived branches, rollback by flag-flip.

---

## Phase 0 — Give the map the space it needs

**Why this exists:** the single biggest complaint about today's view is that the map is too small. No amount of rendering work fixes that if the container is cramped. Phase 0 changes the page layout, not the renderer, so it can ship immediately against the **existing** map component and pay off before any of Phases 0.5–6 land.

**Independence:** stands alone. Layout change only.

**Goal:** promote the map to the top of the telemetry page and give it 50% of the page width (centered). The trace charts move below the map at full width.

**Tasks:**
1. Restructure the telemetry page so the map is the **first** element (top of page, above the trace charts).
2. Allocate the map **50% of the page content width** at desktop breakpoints, **centered** with `margin: 0 auto`.
3. Map height: start at **`min(60vh, 720px)`**, floor of 420px.
4. Below the desktop breakpoint (`< 1024px`), the layout stacks: map full-width on top, charts below it also full-width. Map height stays the same formula.
5. Charts container: **100% width**, displayed below the map (not side-by-side).
6. **Do not** touch the map renderer itself in this phase.

**Acceptance (executable tests):**
- Visual regression test: at a 1440×900 viewport, the map's bounding box is between 700px and 740px wide and between 700px and 740px tall, **centered horizontally**.
- Visual regression test: at a 768×1024 viewport, the map is full-width (≥ 720px wide) and stacked above the charts.
- Render test: the existing renderer mounts and paints without errors in the new container. Pixel-diff against the pre-change render is permitted to differ in scale only, not in content.
- Layout test: charts container is 100% width below the map (not side-by-side).

**Decision gate after Phase 0:** look at the result. If 50% width feels right, leave it. If the map still feels small, bump to 60% or 66% (one-line CSS change) before continuing. Document whichever final share you settled on.

**Layout decision:** We chose to place charts at 100% width **below** the map rather than 50% side-by-side. This gives the map visual prominence as the primary comparison tool while keeping charts readable at full width. The map is centered to emphasize it as the focal point.

**Out of scope:** anything that touches the renderer.

---

## Phase 0.1 — Renderer responds to container size (pure refactor)

**Why this exists:** Phase 0's caveat ("fix only hardcoded sizes if you find them") is a renderer change masquerading as a layout change. We separate it cleanly so Phase 0 stays a pure CSS commit and Phase 0.1 is a pure no-visible-change refactor.

**Independence:** stands alone, but only meaningful after Phase 0 has resized the container. If the existing renderer is already fully responsive, this subphase is empty and gets skipped explicitly with a one-line PR ("verified: no hardcoded dimensions, no work needed"). That's a valid delivery.

**Goal:** the existing renderer, with **no behavior changes**, fills any container size between 320px and 2000px wide without distortion.

**Tasks:**
1. Audit the existing renderer for hardcoded pixel dimensions, hardcoded font sizes, fixed canvas sizes, etc.
2. Replace each hardcode with a value derived from the container (or from `devicePixelRatio` where appropriate).
3. No coloring changes, no label changes, no interaction changes. If you find yourself "improving" something, stop — that's a different subphase.

**Acceptance (executable tests):**
- Screenshot test: render at 320px, 768px, 1024px, 1440px, and 2000px container widths. All five render without overflow, distortion, or clipped labels.
- Pixel-diff test against the pre-change renderer at the original size: **identical**. (If it's not identical, you changed behavior — that's a different subphase.)

**Out of scope:** anything visible.

---

## Phase 0.5 — Walking skeleton: two laps, one map, any rendering

**Why this exists:** before the heatmap, before the ribbons, before any of the rich rendering, we want **something a user can use to compare two laps on one map**. The crappiest version of this answers a real user question ("where did B differ from A?") that nothing currently answers. Every later subphase becomes a *visible upgrade* to a thing users are already using, not a step toward a feature they've never seen.

**Independence:** stands alone. This is the foundation every later subphase builds on, but it ships as a real, usable feature on its own. Feature flag `features.mapWalkingSkeleton`.

**Goal:** draw both laps as 1px polylines in their accent colors on the same canvas, fitted to view. No heatmap, no ribbons, no interaction.

**Tasks:**
1. Create a `<TrackHeatmapMap>` component with a canvas sized to its container (use `ResizeObserver`).
2. Implement `fitToView(samples, padding)` that returns a world→screen transform fitting both laps' bounding box with `padding` px of margin.
3. Draw Lap A as a 1px polyline in `lapA.color`.
4. Draw Lap B as a 1px polyline in `lapB.color`.
5. Draw a short white perpendicular tick at `s = 0` on Lap A (start/finish marker).
6. That's it.

**Acceptance (executable tests):**
- Render test: both polylines appear on the canvas, in the right colors, at the right scale.
- Render test: `fitToView` correctly bounds both laps with the specified padding (assert the transform numerically against a known fixture).
- Resize test: a `ResizeObserver` fires and the canvas re-fits without distortion. Aspect ratio is preserved.
- Visual smoke test: a real lap pair from the fixtures renders recognizably as the correct track shape.

**Out of scope:** heatmap colors, ribbons, the `s`-based lookup, any interaction.

---

## Phase 1a — Heatmap ribbon, single lap

**Why this exists:** the heatmap ribbon is the visual centerpiece of the whole feature. Get it right for **one** lap first, with no cross-lap complexity, so when something is wrong we know it's the ramp or the extrusion, not the alignment.

**Independence:** depends on Phase 0.5's component existing and on the `fitToView` helper. Feature flag `features.mapHeatmapSingleLap`. When flipped on, Lap A's polyline upgrades to a heatmap ribbon; Lap B remains a 1px polyline.

**Goal:** Lap A renders as a properly-colored heatmap ribbon. Lap B is untouched.

**Tasks:**
1. Implement `colorForNet(net: number): string` and the 256-entry LUT from §0.2. Export both from their own module.
2. Implement `drawRibbon(ctx, points, offsetPx, widthPx, colorAt)`:
   - `points` is the lap's centerline (Lap A's `(x, y)`).
   - For each segment `i → i+1`, compute the unit normal, extrude by `offsetPx ± widthPx/2`, fill the quad with `colorAt(i)`.
   - Use `ctx.beginPath` + `lineTo` per quad, fill per quad. Do **not** try to do a single path with one fill — every segment has its own color.
3. Add a 1px darker stroke on each side of the ribbon for legibility.
4. Replace Lap A's polyline from Phase 0.5 with the ribbon. Lap B stays as a polyline.

**Acceptance (executable tests):**
- Unit test: `colorForNet(-1) === '#0a3d91'`, `colorForNet(0) === '#2a3340'`, `colorForNet(1) === '#0f7a2e'`, exact match.
- Unit test: `colorForNet(-0.5)` is closer in OKLCh distance to the brake endpoint than to neutral; `colorForNet(0.5)` is closer to the throttle endpoint than to neutral.
- Unit test: the 256-entry LUT, when sampled at exact integer positions, matches `colorForNet` to within rounding.
- Render test: at a known fixture lap, sampled pixels at known braking-zone positions are in the brake-blue half of the ramp; sampled pixels at known throttle-zone positions are in the throttle-green half.
- Visual: brake zones unmistakably blue, throttle zones unmistakably green, coasting zones fade into the background.

**Out of scope:** Lap B as a ribbon, the `s`-based lookup, side-by-side offset.

---

## Phase 1b — `s`-based cross-lap alignment, with debug overlay

**Why this exists:** the riskiest piece of this whole project is the cross-lap alignment by distance `s`. If Lap A and Lap B's distance parameterizations disagree (GPS drift, different lap-start triggers, sample-rate skew), the side-by-side comparison will look wrong everywhere and we won't know which downstream thing broke. We surface this with a **diagnostic** before we make it cosmetic.

**Independence:** depends on Phase 1a. Feature flag `features.mapSAlignment`. The debug overlay is gated behind a separate dev-only flag and never ships to production.

**Goal:** prove the `s`-lookup works on real data. No cosmetic change to what users see — Lap B is still a polyline, Lap A is still the single ribbon.

**Tasks:**
1. Build a `sLookup(lap: Lap)` helper that, given a target `s`, returns the interpolated sample on that lap via binary search + linear interpolation between adjacent samples.
2. In dev mode (behind a separate flag), render debug tick marks every 100m on **both** laps' polylines, derived via `sLookup`. Each tick is labeled with its `s` value.
3. Add a dev-mode assertion that runs on lap load: verify `s` is strictly monotonic. Hard-fail loudly in dev if not. (Out-of-scope handling deferred to upstream pipeline — but we want to know.)
4. Manually verify by eye on at least two real lap pairs that the 100m ticks line up at corner entries and exits on both ribbons.

**Acceptance (executable tests):**
- Unit test: `sLookup` on a synthetic lap with known samples returns correctly interpolated values at exact and intermediate `s` positions.
- Unit test: `sLookup` is monotonic — querying ascending `s` returns ascending sample indices.
- Property test: for any random `s` in `[0, lap_length]`, `sLookup` returns a sample whose interpolated `s` is within float-epsilon of the query.
- Dev-mode test: the monotonicity assertion fires on a deliberately-corrupted lap fixture.
- Manual visual verification on real data: debug ticks line up across both laps at landmark corners. (This is a human-in-the-loop check; record a screenshot in the PR.)

**Out of scope:** rendering Lap B as a ribbon. We're proving the math first.

---

## Phase 1c — Lap B as the second ribbon (side-by-side)

**Why this exists:** with alignment proven in 1b, we can confidently promote Lap B from polyline to ribbon. If the side-by-side looks wrong now, we know it's the offset/extrusion math, not the data alignment — because 1b already proved the alignment.

**Independence:** depends on Phase 1a and 1b. Feature flag `features.mapDualRibbon`.

**Goal:** both laps rendered as parallel heatmap ribbons. Matches the third panel of reference image 1.

**Tasks:**
1. For each centerline index on Lap A, use `sLookup(lapB, s_A)` to get Lap B's matching sample.
2. Compute `colorAt` for Lap B from the matched samples.
3. Render Lap A's ribbon offset by `-(ribbonWidth + gap)/2` from the centerline (inside).
4. Render Lap B's ribbon offset by `+(ribbonWidth + gap)/2` from the centerline (outside).
5. Draw order: background → Lap A ribbon → Lap B ribbon → start/finish marker.

**Acceptance (executable tests):**
- Render test: both ribbons visible, parallel, with the correct heatmap coloring.
- Render test: ribbons do not overlap; the gap between them is `gap` pixels at all zoom levels.
- Render test: Lap A is consistently on the inside (left of travel direction) around the whole lap.
- Visual smoke test: a real lap pair renders matching the reference image's parallel-ribbon style.
- Resize test: re-fits without distortion, aspect ratio preserved.

**Out of scope:** zoom, pan, hover, highlight, legend, lap labels.

---

## Phase 2 — Zoom and pan

**Independence:** depends on Phase 1c. Feature flag `features.mapZoomPan`. If never shipped, Phase 1c remains usable as a static overview.

**Goal:** the map becomes navigable. The visual from Phase 1c is preserved; only the transform changes.

**Tasks:**
1. Maintain transform state `{ scale, tx, ty }` (prefer a ref + manual redraw for perf).
2. **Wheel to zoom:** zoom centered on the cursor. Clamp `scale` to `[1, 40]`. Use a multiplier of `1.0015 ** -deltaY`.
3. **Drag to pan:** pointer down + move updates `tx, ty`. Use Pointer Events (not Mouse Events) for touch and pen support. Set `cursor: grab` / `grabbing`.
4. **Double-click to reset** to the fit-to-view transform.
5. Redraw on every transform change.
6. Ribbon width in **screen pixels** stays constant: when computing the extrusion, divide the world-space half-width by `scale`, or extrude in screen space after projecting the centerline.
7. Add a small zoom indicator in a corner: `1.0× … 40×`. No buttons yet.

**Acceptance (executable tests):**
- Perf test: a scripted pan across the lap for 2 seconds at 60Hz. No frame exceeds 16ms (p99) on the reference machine spec documented in the repo. If perf fails here and didn't fail in Phase 1c, you have a transform bug, not a rendering bug.
- Interaction test (Playwright or equivalent): wheel events change scale within the clamp; pointer-drag changes tx/ty 1:1 with movement; double-click resets to fit-to-view transform exactly.
- Render test: at `scale = 1`, `scale = 10`, and `scale = 40`, the ribbon thickness in screen pixels is constant (measured at known sample positions; assert within ±0.5px).
- Touch test: pointer events fire correctly from a simulated touch.

**Out of scope:** zoom buttons, keyboard shortcuts, minimap, highlight band.

---

## Phase 3 — Lap legend and identification

**Independence:** purely additive over Phase 1c. Does not require Phase 2. Feature flag `features.mapLegend`. Can be implemented in parallel with Phase 2 if useful — but only one of them merges to main at a time.

**Goal:** make it obvious which ribbon is which lap.

**Tasks:**
1. Add a legend in the top-left of the map (absolute-positioned over the canvas):
   - Lap A: small swatch in `lapA.color` + label.
   - Lap B: small swatch in `lapB.color` + label.
2. Render a 1px outline along **the outer edge of each ribbon** in that lap's accent color, full lap.
3. Add a tiny color-ramp legend in the top-right: a horizontal gradient strip `dark blue → neutral → dark green` with labels `Brake` and `Throttle` at the ends. About 160×16 px.

**Acceptance (executable tests):**
- Render test: legend is visible at the top-left with both lap labels and swatches.
- Pixel test: a pixel sampled at the right end of the ramp legend equals `colorForNet(1)` exactly. A pixel sampled at the left end equals `colorForNet(-1)` exactly. A pixel sampled at the middle equals `colorForNet(0)` exactly.
- Render test: each ribbon's outer edge is outlined in its lap accent color. Inner edges are not outlined.

**Out of scope:** statistics, deltas, hover tooltips.

---

## Phase 4 — Hover crosshair and per-lap readout

**Independence:** depends on Phase 1c renderer and the `sLookup` from Phase 1b. Most usefully shipped after Phase 2 so users can hover at useful zoom levels, but technically independent. Feature flag `features.mapHover`.

**Goal:** point at a spot on the map and see the underlying values for both laps.

**Tasks:**
1. On pointer move over the canvas, compute the nearest point on **Lap A's centerline** in world space (use a precomputed spatial index — a uniform grid keyed by world coords is plenty for a single lap; quadtree is overkill).
2. From that nearest point, get the corresponding `s` on Lap A. Look up Lap B's matching sample via `sLookup`.
3. Draw a short white perpendicular tick across **both** ribbons at the matched location (same style as start/finish, but 1px).
4. Render a small readout panel near the cursor (offset by 12px, flipped to keep it on-screen near edges):
   - Top row: `Distance: 1432 m  •  Lap A: 7:24 split  •  Lap B: 7:31 split` (monospace, subtle)
   - Two rows: `Lap A — Throttle 87% / Brake 0%` and `Lap B — Throttle 62% / Brake 12%`.
   - Lap labels in lap accent colors; throttle/brake numbers in green/blue from the ramp at full saturation.
5. Hide the readout when the pointer leaves the canvas.
6. Coalesce updates with `requestAnimationFrame` to avoid flicker.

**Acceptance (executable tests):**
- Interaction test: pointer-move over a known position on the canvas produces a readout with the expected `s`, throttle, brake values (assert against fixture data).
- Render test: the perpendicular tick is geometrically perpendicular to the local racing line (compute the tangent at the sample and assert dot-product with the tick direction is within epsilon of zero).
- Interaction test: during a pointer-drag (pan), the readout is hidden.
- Render test: the readout flips horizontally/vertically near canvas edges to stay on-screen.

**Out of scope:** click-to-pin, multi-point comparison.

---

## Phase 5a — Linked highlight band from trace charts

**Independence:** depends on Phase 1c. The map accepts an **optional** `visibleRange` prop. When absent or `undefined`, this subphase is a no-op. Feature flag `features.mapLinkedHighlight`. Ship before the trace charts pass the prop — the feature lights up the day the trace-chart team wires it.

**Goal:** when the user zooms or scrolls the existing trace charts, the corresponding stretch of track lights up on the map without obscuring the heatmap.

**Tasks:**
1. Subscribe to `visibleRange: { sStart, sEnd }`. Charts lead, map follows.
2. Compute the polyline along Lap A's centerline between `sStart` and `sEnd`. Same for Lap B (via `sLookup`).
3. Render the highlight as a **translucent overlay band** along both ribbons:
   - Stroke a polyline **5px wider than the ribbon on each side** in `rgba(255,255,255,0.18)`.
   - Composite with `globalCompositeOperation = 'lighten'` so it brightens the heatmap rather than tinting it. This preserves brake/throttle colors. Do **not** use `multiply` or a flat overlay.
   - Add two crisp 1px white perpendicular ticks at the start and end of the band, full ribbon width plus 6px overshoot top and bottom.
4. The rest of the lap stays at full saturation — **do not** dim the unhighlighted portion.

**Acceptance (executable tests):**
- Event-loop test: after firing a `visibleRange` change, the next paint completes within 100ms (p95). Measured under headless browser with scripted events.
- Render test: with `visibleRange = { sStart: 400, sEnd: 800 }`, the highlight band's geometric start and end correspond to those `s` values on Lap A's centerline (verified by intersecting the start tick with a known sample position).
- Pixel test: a pixel inside the highlight band at a known throttle-zone position is still in the throttle-green half of the ramp (the composite brightens, does not desaturate).
- Render test: with no `visibleRange` prop, the map renders identically to Phase 4 (pixel-diff against a baseline screenshot).
- Resize test: resizing the window does not change the highlight's `s` boundaries. Track-space, not screen-space.

**Out of scope:** auto-pan to highlight, two-way binding, delta coloring, sector boundaries.

---

## Phase 5b — Click-to-scrub (reverse binding)

**Independence:** depends on Phase 5a. Feature flag `features.mapClickToScrub`. Adds the reverse direction of the chart↔map link.

**Goal:** clicking on the map at a point emits the corresponding `s` to the parent via `onMapClickS`.

**Tasks:**
1. On click (not drag), compute the nearest `s` on Lap A's centerline (reusing the spatial index from Phase 4).
2. Call `onMapClickS(s)` if provided.
3. If no callback is provided, this subphase is a no-op visually — but the click still computes (so a dev can wire it later).

**Acceptance (executable tests):**
- Interaction test: clicking at a known canvas position fires `onMapClickS` with the expected `s` (within sample-resolution epsilon).
- Interaction test: a click that is the end of a drag does **not** fire `onMapClickS`. Distinguishing click from drag uses a movement threshold (default 4px) plus a time threshold (default 250ms).
- Contract test: when `onMapClickS` is `undefined`, clicks do not throw.

**Out of scope:** scrubbing playback, multi-point selection.

---

## Phase 6 — Polish (a bag of independent deliveries)

Each item below is **its own subphase**, with its own feature flag, its own merge, its own acceptance run. Pick and ship in any order, any subset. None block each other.

**6.1 DPR-aware canvas** *(depends on: Phase 0.5)* — size the backing store to `devicePixelRatio` so ribbon edges and ticks are crisp on retina. Acceptance: at DPR=2, a 1px tick measures 1 CSS pixel and 2 device pixels.

**6.2 Performance pass** *(depends on: Phase 1c)* — if either lap has >10k samples, downsample for rendering using Ramer–Douglas–Peucker with epsilon tuned so the visual is indistinguishable from full data at max zoom. Keep full-resolution data for hover and `sLookup`. **Threshold note:** 10k samples corresponds to ~100 seconds at 100Hz logging — real-world long-track laps can hit this. Tune against real fixtures. Acceptance: render time at 12k-sample lap is within 1.2× the render time at 6k-sample lap.

**6.3 Color-blind safe alt ramp** *(depends on: Phase 1a)* — second ramp (orange→neutral→teal) behind a setting. Same `colorForNet` contract, different LUT. Acceptance: switching the ramp prop swaps all heatmap colors and the legend gradient atomically; no mixed state.

**6.4 Keyboard controls** *(depends on: Phase 2)* — `+`/`-` to zoom centered on viewport, arrow keys to pan, `0` to reset. Acceptance: each binding produces the expected transform change.

**6.5 Zoom button stack** *(depends on: Phase 2)* — `+ / − / ⌖` buttons in the bottom-right. Same actions as keyboard.

**6.6 Minimap inset** *(depends on: Phase 2)* — 120×80 px inset in bottom-left showing the full track at fit-zoom with a viewport rectangle. Draggable. Hide when zoom ≤ 1.05×.

**6.7 Auto-pan when highlight is small** *(depends on: Phase 5a)* — when the highlight covers <5% of lap length and is currently outside the viewport, auto-pan (no zoom change) to center it. **Honors `prefers-reduced-motion`: snap instead of tween.** This was originally bundled into Phase 5; pulled out here because it changes the user's view without them asking, which is exactly the kind of feature that gets disabled in week two. Ship it standalone so it can be reverted standalone. Acceptance: scripted test with `visibleRange` that's both small and off-screen triggers a pan; the same range when already on-screen does not.

**6.8 Sector jump** *(depends on: Phase 5a + sector data)* — `[` and `]` move the highlight to the prev/next sector if sector data is available. Skip this item if your data source doesn't expose sectors.

**Acceptance per item:** the specific item works as described, plus no regression in any earlier subphase. After every 2–3 items, run a smoke test: pan + zoom + hover + chart-brush for 30 seconds, no dropped frames on a mid laptop.

---

## What an agent should not do

- Do not introduce a charting library (D3, Plotly, Chart.js, etc.) for this map. Canvas + a tiny transform helper is the whole stack.
- Do not draw the heatmap as a polyline with `strokeStyle` changes per segment. That fights anti-aliasing at segment joins and produces visible seams. Use filled quads as specified in Phase 1a.
- Do not dim the unhighlighted lap portion in Phase 5a. The whole-lap heatmap is the value.
- Do not start a later subphase before its declared dependencies are passing acceptance.
- Do not couple this component to the trace-chart implementation. It consumes a `visibleRange` (optional) and emits an optional `onMapClickS` callback. That's the entire contract.
- Do not bundle subphases. One subphase, one delivery. If two feel small enough to combine, that's a sign you should ship the first one even faster, not combine them.
- Do not optimize Phase 1a or 1c until a later subphase reveals a real perf problem. YAGNI.
- Do not write a generic `<TrackMap>` abstraction. Write `<TrackHeatmapMap>` with two specific laps. If a third use case appears, refactor then.
- Do not let any file exceed 437 lines. Not even by one line. Not even temporarily.
- Do not mix refactor commits with behavior commits.
- Do not ship a spike. Spikes get thrown away; only stabilized, tested implementations ship.

---

## Component API (final shape, for reference)

```ts
type TrackHeatmapMapProps = {
  lapA: Lap;
  lapB: Lap;
  visibleRange?: { sStart: number; sEnd: number };  // from trace charts
  onMapClickS?: (s: number) => void;                 // Phase 5b
  ribbonWidthPx?: number;   // default 8
  ribbonGapPx?: number;     // default 2
  colorRamp?: 'default' | 'cbSafe';
};
```

That's the whole external surface. Everything else is internal.
