# Web Refactor — Step 8 Handoff

**Date:** 2026-05-13  
**Status:** Step 7 complete (`circuitMap.js` extracted, all 81 tests passing)  
**Next:** Step 8 — Extract `panels.js` (panel SVG rendering)

---

## Current State

### Files
| File | Size | Role |
|------|------|------|
| `web/js/main.js` | ~58 KB, 1310 lines | App entry point, DOM rendering, event handlers |
| `web/js/appState.js` | 2.6 KB | Global state (`state`, `getCurrentMapMode`, `setCurrentMapMode`, panel order persistence) |
| `web/js/utils.js` | 5 KB | String helpers, formatting, persistence, error/badge display |
| `web/js/pipeline.js` | 18 KB, 432 lines | Data pipeline (loading, resampling, Δt computation, geometry helpers) |
| `web/js/circuitMap.js` | 7.8 KB, 167 lines | **NEW** — Circuit map rendering (outline, heatmaps, legend, zoom arc) |
| `web/compare.html` | — | Single-page app (no build step, ESM imports from CDN) |

### Test Status
```
M5:     25/25 ✔
M6:     26/26 ✔
F1F2:   13/13 ✔
Extras: 17/17 ✔
────────────────
Total:  81/81 passing
```

**Note:** Tests run via HTTP server (`scripts/lib/test-server.js`). Do not test by opening HTML files directly in browser.

---

## What Changed in Step 7

### New Module: `web/js/circuitMap.js`

Extracted circuit map rendering from `main.js`:

```javascript
// Constants
export const MAP_SIZE;       // 250
export const MAP_PAD;        // 20
export const HEATMAP_RAMPS;  // speed/brake/throttle colour ramps
export const HEATMAP_CHANNELS; // mode → column mapping

// Functions
export function renderCircuitMap(currentTrackX, currentTrackZ, trackTransform, currentZoomRange, currentMaxDist, currentSessionBins);
export function renderHeatmapSegments(mode, currentTrackX, currentTrackZ, trackTransform, currentSessionBins);
export function renderMapLegend(mode, currentTrackX, currentSessionBins);
export function updateZoomArc(currentTrackX, currentTrackZ, trackTransform, currentZoomRange, currentMaxDist);
```

### Changes to `main.js`

**Added import:**
```javascript
import { renderCircuitMap, renderHeatmapSegments, renderMapLegend, updateZoomArc,
         HEATMAP_RAMPS, HEATMAP_CHANNELS } from './circuitMap.js';
```

**Removed:** ~170 lines of circuit map rendering code (constants + 4 functions).

**Remaining in `main.js`:**
- `renderPanel`, `renderDtPanel` — SVG panel rendering (~350 lines)
- `renderAll` — master orchestrator (~190 lines)
- Picker UI logic (`rebuildPickers`, `updateCompareBtn`, `parsePickerValue`)
- File loading orchestration (`loadFile`, `loadSidecar`, `loadDeltabestCsv`)
- Session list UI (`addSessionEntry`, `refreshSessionListBadges`)
- Cursor/tooltip logic (`updateCursorPosition`, `updateCursorDot`)
- All event handlers (mouse, keyboard, drag-and-drop)
- Debug hooks (`window.__resamplerDebug`, etc.)

---

## Learnings from Step 7

### 1. Parameter Passing for State-Dependent Functions

The original circuit map functions read module-scope state directly (e.g., `currentTrackX`, `currentSessionBins`). When extracting, we chose to **pass state as parameters** rather than have the module import `appState.js`. This keeps the module pure and testable.

**Pattern:**
```javascript
// ❌ Don't rely on module-scope state from main.js
function renderCircuitMap() {
  if (!currentTrackX || !currentTrackZ) return;  // undefined!
}

// ✅ Pass state explicitly
export function renderCircuitMap(currentTrackX, currentTrackZ, trackTransform, currentZoomRange, currentMaxDist, currentSessionBins) {
  if (!currentTrackX || !currentTrackZ) return null;
}
```

**Lesson:** For extracted rendering modules, pass state as parameters. This makes the module self-contained and easier to test.

### 2. Function Signature Consistency

When extracting functions that call other extracted functions, ensure **all parameters are threaded through**. The initial extraction missed passing `currentSessionBins` to `renderHeatmapSegments` inside `renderCircuitMap`, causing heatmap tests to fail.

**Lesson:** After extraction, verify that internal function calls pass all required parameters. Run tests immediately to catch these issues.

### 3. JSDoc Comments Must Be Complete

A malformed JSDoc comment (missing `/**` opening) caused esbuild to fail with a cryptic error. Always ensure JSDoc blocks are complete:

```javascript
/**
 * Function description
 * @param {Type} name - Description
 */
export function myFunction(name) { ... }
```

---

## Step 8: Extract `panels.js`

### Functions to Extract

| Function | Lines in main.js | Description |
|----------|------------------|-------------|
| `renderPanel(def, bins, maxDist, sectorDists, zoomRange)` | ~130 lines | Renders all non-Δt telemetry panels (Speed, Throttle, TC, Brake, ABS, RPM, Gear, Steering, Slip) |
| `renderDtPanel(def, dtBins, maxDist, sectorDists, zoomRange, overlapRange)` | ~100 lines | Renders the Δt panel with overlap clipping |

### Constants to Move

| Constant | Current Location | Description |
|----------|------------------|-------------|
| `SVG_W`, `PAD`, `PLOT_W` | `main.js` lines ~40-42 | SVG layout constants (shared with circuitMap.js) |

**Note:** `PANEL_DEFS` stays in `main.js` — it's a rendering concern but also defines the panel order and structure that the rest of the app depends on. Moving it would require updating many imports.

### Constants to Keep in `main.js`

- `PANEL_DEFS` — panel definitions (used by `renderAll` and UI logic)
- `COLUMNS` — parquet column names (used by file loading)

### Dependencies

`panels.js` will import:
```javascript
import { SVG_W, PAD, PLOT_W } from './constants.js';  // or keep in main.js
import { niceRange, buildPolylinePts, computeNiceYTicks } from './pipeline.js';
```

**Decision:** `SVG_W`, `PAD`, `PLOT_W` are used by both `panels.js` and `main.js` (event handlers). They can either:
1. Stay in `main.js` and be imported by `panels.js` (creates circular dependency risk)
2. Move to a new `constants.js` module (cleanest, but adds a new file)
3. Stay in `main.js` and be passed as parameters to `renderPanel`/`renderDtPanel`

**Recommended:** Option 2 — create `constants.js` with SVG layout constants. This follows the original plan and keeps modules clean.

---

## Recommended Approach for Step 8

### Phase 1: Create `constants.js`

Extract SVG layout constants that are shared between modules:

```javascript
// web/js/constants.js
export const SVG_W = 900;
export const PAD = { top: 6, right: 20, bottom: 24, left: 58 };
export const PLOT_W = SVG_W - PAD.left - PAD.right;
```

Update imports in `main.js` and `circuitMap.js` (if needed).

### Phase 2: Extract `panels.js`

Create `web/js/panels.js` with:
- `renderPanel(def, bins, maxDist, sectorDists, zoomRange, svgW, pad, plotW)`
- `renderDtPanel(def, dtBins, maxDist, sectorDists, zoomRange, overlapRange, svgW, pad, plotW)`

**Parameter strategy:** Pass `SVG_W`, `PAD`, `PLOT_W` as parameters to avoid importing `constants.js` in both modules. Or import `constants.js` in both — either works.

### Phase 3: Update `main.js`

- Add import for `renderPanel`, `renderDtPanel` from `panels.js`
- Remove the extracted functions
- Update `renderAll` to call the imported functions

---

## Validation Checklist for Step 8

Before considering Step 8 complete:

- [ ] Run `npm run build` — verify no esbuild errors
- [ ] Run `npm test` — all 81 assertions must pass
- [ ] Open `dist/compare.html` in browser — verify:
  - All 10 panels render (Speed, Throttle, TC, Brake, ABS, RPM, Gear, Steering, Slip, Δt)
  - Panel labels show correctly
  - X-axis labels appear only on bottom panel
  - Y-axis ticks and grid lines render
  - Sector markers (S2, S3) appear on all panels
  - Δt panel shows sector Δt readouts and lap-end value
  - Activity strips (ABS/TC) render on Brake/Throttle panels
  - Zoom interaction works (drag to zoom, dblclick/Esc to reset)
  - Tooltip follows cursor and shows correct values
- [ ] Check console for "undefined" errors (scope issues)

**Quick smoke test:**
```bash
npm run build && npm test
open dist/compare.html  # Manual verification
```

---

## Debug Tips

### Panel Not Rendering
1. Check that `renderPanel` is being called with correct `bins` structure
2. Verify `def.channels` array is populated
3. Check that `toX`/`toY` functions produce valid coordinates

### Missing Data in Panels
1. Verify `binsMap` is built correctly in `renderAll`
2. Check that `currentSessionBins`/`currentRefBins` are populated before `renderAll` calls `renderPanel`
3. Use `window.__resamplerDebug` to inspect resampled data

### X-Labels on Wrong Panel
1. The `showXLabels` flag is set on the last visible non-Δt panel
2. Verify `lastNonDtId` logic accounts for hidden panels (Slip, ABS, TC)

### Sector Markers Missing
1. Check `sectorDists` is passed to `renderPanel`/`renderDtPanel`
2. Verify `deriveSectorDistances` returns valid distances
3. Sector markers are clipped to panel's plot area via `clip-path`

---

## Estimated Impact

| Metric | Before | After | Δ |
|--------|--------|-------|---|
| `main.js` lines | 1310 | ~1050 | -260 |
| `panels.js` lines | — | ~250 | +250 |
| `constants.js` lines | — | ~10 | +10 |
| Total files | 5 | 7 | +2 |

**Reduction:** `main.js` reduced by ~20% (1310 → 1050 lines)

---

## Next Steps After Step 8

Depending on progress:
- **Step 9:** Extract `ui.js` (~350-400 lines) — highest risk due to event handler scope rules
- **Step 10:** Extract `pickers.js` (~150 lines) — medium risk, DOM manipulation
- **Step 11:** Extract `dataTransforms.js` (~200 lines) — requires splitting DOM orchestration from pure parsing
- **Step 12:** Final cleanup — create `main.js` as thin entry point, update `compare.html`

**Ultimate goal:** `main.js` under 500 lines, with clear separation:
- `pipeline.js` — data loading/processing (done ✓)
- `circuitMap.js` — circuit map rendering (done ✓)
- `panels.js` — telemetry panel rendering (Step 8)
- `ui.js` — user interaction (pickers, file loading, drag-reorder)
- `pickers.js` — picker/session-list DOM projection
- `dataTransforms.js` — pure data parsing
- `constants.js` — shared constants
- `main.js` — app entry point, `renderAll` orchestration, debug hooks

---

## Appendix: File Sizes After Step 7

```
web/js/main.js        1310 lines  (~58 KB)
web/js/appState.js      59 lines  (~2.6 KB)
web/js/utils.js        129 lines  (~5 KB)
web/js/pipeline.js     432 lines  (~18 KB)
web/js/circuitMap.js   167 lines  (~7.8 KB)
──────────────────────────────────────────
Total:                2097 lines  (~91 KB)
```

**Reduction from original:** `main.js` reduced from 1869 → 1310 lines (-30%)

---

## Notes

- **No behavioural changes in Step 7** — pure extraction refactor
- `circuitMap.js` functions take **explicit parameters** for state (not module-scope imports)
- Keep `PANEL_DEFS` in `main.js` for now (used by `renderAll` and UI logic)
- Keep `renderAll` in `main.js` (orchestrates across modules)
- Step 8 is **medium risk** — panel rendering is self-contained but has many edge cases (zoom, sectors, activity strips)
