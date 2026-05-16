# Refactor Plan — `main.js` back under 437 lines

> **Scope:** Pure refactor. No behavior change. Each step lands as one `refactor:` commit, with `npm test` and `npm run build` green between every step.

## Current state

- `web/js/main.js`: **543 lines** (106 over the 437 hard ceiling in `AGENTS.md`).
- Structure (line ranges):

| Range | Section | Lines |
|------:|---------|------:|
| 1–58 | Imports | 58 |
| 60–76 | Module-level mutable state | 17 |
| 77–332 | `renderAll()` | 256 |
| 342–503 | `renderTrackHeatmapMap()` | 162 |
| 507–523 | `getRenderState()` | 17 |
| 525–543 | App init + `installDebugHooks` | 19 |

- All other modules are within budget. The over-spill lives entirely in `renderAll()` and `renderTrackHeatmapMap()`.

## Working agreements for this refactor

1. **One step, one commit, one `refactor:` prefix.** Never bundle behavior change with a move.
2. **Green between every step.** `npm test` exits 0 and `npm run build` succeeds before the commit.
3. **Identity test:** after each step the rendered DOM and canvas pixels must be byte-identical to the previous step. The existing test suite (250+ assertions, including pixel-level checks for ribbons/legends/highlight) is our regression net.
4. **YAGNI.** Don't generalise. Each extraction names exactly one job. No "while I'm here."
5. **Stop at green and under-ceiling.** As soon as `main.js ≤ 437`, the refactor phase is done. Steps after that are optional polish, not part of this delivery.

## Step-by-step plan

Each step lists: target lines saved, target file, what moves, and the test command that proves green.

### Step 1 — Dedupe the lapA/lapB builder inside `renderTrackHeatmapMap`

**What.** The lapA/lapB object literals are built twice in `renderTrackHeatmapMap`: once for the immediate render (lines ~378–396), once again inside the `initTrackHeatmapResize` callback (lines ~458–477). Same for the `opts` object (lines ~412–419 vs ~478–493).

**Move to:** stays in `main.js` for now — just inline helpers `buildLaps()` and `buildOpts()` at function scope.

**Lines saved:** ~25 (de-dup, not extraction).

**Risk:** very low — pure local refactor.

**Green check:** `npm test && npm run build`.

**Resulting `main.js`:** ~518 lines.

---

### Step 2 — Extract `renderTrackHeatmapMap` to `trackHeatmapController.js`

**What.** Move the entire `renderTrackHeatmapMap()` function (now ~135 lines after Step 1) plus the module-level refs it owns (`trackHeatmapObserver`, `mapInteraction`, `mapHover`) into a new file.

**New module API:**

```js
// trackHeatmapController.js
export function createTrackHeatmapController(getMapState) { ... }
// returns { render(), getMapInteractionState(), getMapHoverState() }
```

`getMapState` is a callback that returns `{ currentTrackX, currentTrackZ, currentRefTrackX, currentRefTrackZ, currentSessionBins, currentRefBins, currentLapARaw, currentLapBRaw, currentZoomRange }` — i.e. the bits of main.js state the controller reads. main.js keeps owning the state; the controller is purely a renderer that reads via the callback.

**Lines saved:** ~140 from `main.js`.

**Risk:** medium. The controller has to expose enough state for `cursor.js` and `debugHooks.js` to still work (they currently call `renderTrackHeatmapMap` after flag toggles).

**Green check:**
- `npm test` — all 250+ assertions still pass (this is the regression net).
- `npm run build`.
- Manual smoke: open `dist/compare.html`, toggle each map feature flag via the dropdown, confirm the map re-renders.

**Resulting `main.js`:** ~378 lines (under the ceiling ✅ — refactor goal met).

> **Stop here if green.** Steps 3+ are optional polish that further improves coherence but are not required to satisfy the ceiling.

---

### Step 3 (optional) — Extract channel resampling from `renderAll`

**What.** The two resampling loops in `renderAll` (channel resampling: lines ~117–145; activity-strip resampling: lines ~147–156; track-coord resampling: lines ~158–175) are pure data transforms. Extract a single function:

```js
// pipeline.js (already 432 lines — keep room) OR new resampleAll.js
export function resampleLapPair(sessionEntry, refEntry, sKeep, rKeep, sDistRaw, rDistRaw, maxDist, panelDefs) {
  return { sessionBins, refBins, trackX, trackZ, refTrackX, refTrackZ };
}
```

**Lines saved:** ~55 from `main.js`.

**Risk:** low. Pure function, no DOM. The output object replaces direct module-state writes one-for-one.

**Green check:** `npm test && npm run build`.

**Resulting `main.js`:** ~323 lines.

---

### Step 4 (optional) — Extract lap-raw-array building

**What.** The `currentLapARaw` / `currentLapBRaw` Float64Array construction (lines ~177–194) is a pure data transform. Extract:

```js
// pipeline.js or resampleAll.js
export function buildLapRaw(entry, keep, distRaw) {
  return { s, x, z, throttle, brake }; // all Float64Array
}
```

**Lines saved:** ~18.

**Risk:** very low.

**Green check:** `npm test && npm run build`.

**Resulting `main.js`:** ~305 lines.

---

### Step 5 (optional) — Extract lap_time_s and Δt computation

**What.** Lines ~196–220 compute `sLapTimeBins`, `rLapTimeBins`, the forward-clamp, and `currentDtBins`. Extract:

```js
// pipeline.js
export function computeDtPair(sessionEntry, refEntry, sKeep, rKeep, sDistRaw, rDistRaw, maxDist) {
  return { sLapTimeBins, rLapTimeBins, dtBins };
}
```

**Lines saved:** ~25.

**Risk:** very low. Pure function, well-covered by the existing M5 Δt cross-check test.

**Green check:** `npm test && npm run build`. Pay attention to the M5 Δt diff assertion (`max < 500 ms`).

**Resulting `main.js`:** ~280 lines.

---

### Step 6 (optional) — Extract the panel HTML build loop

**What.** Lines ~230–285 build the panel stack (`<div class="panel-wrap">` per id, with label, SVG, slip placeholder, etc.). Extract:

```js
// panels.js (already 283 lines — fine room) OR new panelStack.js
export function renderPanelStack(panelsDiv, panelOrder, panelDefs, bins, ...) {}
```

**Lines saved:** ~55.

**Risk:** medium. Touches DOM. Covered by tests counting panel polylines (M5/M6/F1F2).

**Green check:** `npm test && npm run build`.

**Resulting `main.js`:** ~225 lines.

---

## Decision points

- **After Step 2, evaluate.** If `main.js` is under 437 and reads coherently, stop. The remaining steps (3–6) are nice-to-haves and don't pay for their own risk.
- If after Step 2 the file still feels muddled, do Steps 3–4 (pipeline extractions are cheap and risk-free).
- Save Step 6 for last and only if needed — DOM-touching refactors carry the highest regression risk.

## Artifacts on completion

1. `npm test` exits 0.
2. `npm run build` succeeds; `dist/compare.html` is current.
3. `web/js/main.js` ≤ 437 lines (verify with `wc -l`).
4. `phases/refactor-main-js/learnings.md` — anything that surprised you, especially any state-coupling that fought the extraction.
5. `phases/refactor-main-js/handoff.md` — final line counts per module, new module API summary.
6. Update `NEXT_STEPS.md`: remove the "🚨 Urgent" section, restore the module-structure table to reflect actuals.
7. Commits on `main`, each prefixed `refactor:`.

## Anti-goals

- **Do not change rendered output.** This is a refactor, not a fix.
- **Do not generalise.** No `<TrackMap>`-style abstraction. The controller renders the one specific heatmap. If a second use case appears later, refactor then.
- **Do not introduce new feature flags, options, or props.** The new modules consume exactly what main.js already passes them.
- **Do not bundle a behavior fix into a refactor commit.** If you spot a bug, file it in `NEXT_STEPS.md` and keep moving.
