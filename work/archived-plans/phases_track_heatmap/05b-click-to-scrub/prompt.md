# Phase 05b — Click-to-Scrub (reverse binding)

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 5b from `track-heatmap-spec.md`

**What to do:**
1. Read `track-heatmap-spec.md` section "Phase 5b — Click-to-scrub (reverse binding)"
2. Read `phases/05a-linked-highlight/handoff.md` to understand the current state
3. Implement click-to-scrub: clicking on the canvas map computes the nearest `s` on Lap A's centerline and emits it
4. Write tests first (following `TESTING_LESSONS.md`)
5. Follow XP working agreements in `AGENTS.md`

**Key requirements:**
- Feature flag: `features.mapClickToScrub` (default OFF)
- The map already has a spatial index (uniform grid, 20m cells) built by `createMapHover` in `web/js/mapHover.js` for Phase 4 hover hit-testing. **Reuse it.** Do not build a second spatial index.
- On click (not drag), compute nearest `s` on Lap A's centerline by:
  1. Converting screen click coordinates to world space via `getLastTransform()` (already exported from `trackHeatmapMap.js`)
  2. Querying the existing spatial index for the nearest raw sample point
  3. Using that sample's `s` value
- Distinguish **click from drag** using:
  - Movement threshold: `Math.hypot(dx, dy) < 4` px between `pointerdown` and `pointerup`
  - Time threshold: `< 250ms` between `pointerdown` and `pointerup`
  - If either threshold is exceeded, it's a drag — do **not** fire the click handler.
- The click handler is `onMapClickS(s)` — a callback that `main.js` provides when creating the map interaction. When the callback is absent/undefined, the feature is a no-op (no visual change, no errors).
- **Where to add click detection:** `mapInteraction.js` already tracks `pointerdown`/`pointermove`/`pointerup` for drag. Extend it to detect clicks and call an optional `onClick(sx, sy)` callback. `main.js` then wraps that to do the world→s lookup and call `onMapClickS(s)`.
- Expose the spatial index helpers from `mapHover.js` so `main.js` (or a new small click module) can reuse them without duplicating code. Options:
  - Export `buildGrid` and `findNearest` from `mapHover.js`
  - Or extract them to a new `spatialIndex.js` module (preferred if `mapHover.js` would become incoherent)
  - Keep it simple: one file, one job.

**Architecture notes:**
- `mapInteraction.js` currently takes `(canvas, onChange)`. Add an optional third parameter `onClick(screenX, screenY)`.
- `main.js` creates `mapInteraction` in `renderTrackHeatmapMap()`. When `features.mapClickToScrub` is true, pass a click handler that:
  1. Reads `getLastTransform()`
  2. Converts screen coords to world (invert the affine: `worldX = (sx - offsetX - panX) / (baseScale * userScale) + bounds.minX`, `worldZ = bounds.maxZ - (sy - offsetY - panY) / (baseScale * userScale)`)
  3. Uses the existing grid to find nearest sample → get `s`
  4. Calls `onMapClickS(s)` if provided
- For testing, expose a mock `onMapClickS` on `window` or pass it into the synthetic render in the test.
- The spatial index is rebuilt after each render via `mapHover.rebuild()`. For click-to-scrub, ensure the index is also fresh after render. If `mapHover` is not initialized (flag off), the click handler may need to build its own grid from `currentLapARaw`.

**Acceptance criteria (from spec):**
- Interaction test: clicking at a known canvas position fires `onMapClickS` with the expected `s` (within sample-resolution epsilon).
- Interaction test: a click that is the end of a drag does **not** fire `onMapClickS`. Verify with a `pointerdown` followed by `pointermove` > 4px away, then `pointerup`.
- Contract test: when `onMapClickS` is `undefined`, clicks do not throw.

**Out of scope:**
- Scrubbing playback (no video/audio timeline)
- Multi-point selection
- Wiring `onMapClickS` to actually move the trace-chart cursor (that would couple to the chart implementation; Phase 5b only emits the callback)

**When done:**
- `npm test` passes (all existing tests + new Phase 05b tests)
- `npm run build` succeeds and `dist/compare.html` is current
- `phases/05b-click-to-scrub/learnings.md` exists
- `phases/05b-click-to-scrub/handoff.md` exists
- Commits on `main`, with `refactor:` prefix where appropriate
- Update `phases/PLAN` to mark 05b as DONE
- Update `phases/CURRENT` to the next phase

**Stop at green.** When acceptance passes, commit and stop. Don't start the next phase.
