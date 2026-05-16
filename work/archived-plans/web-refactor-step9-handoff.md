# Web Refactor — Step 9 Handoff

**Date:** 2026-05-13  
**Status:** Step 8 complete (panels.js extracted, contextual Y-axis fix, RENDER_DESIGN.md created)  
**Next:** Step 9 — Extract `ui.js` (user interaction: event handlers, file loading, cursor/tooltip)

---

## Current State

### Files
| File | Lines | Size | Role |
|------|-------|------|------|
| `web/js/main.js` | ~1066 | ~45 KB | App entry point, DOM rendering, event handlers |
| `web/js/appState.js` | 59 | ~2.6 KB | Global state (`store`, `panelOrder`, map mode) |
| `web/js/utils.js` | 129 | ~5 KB | String helpers, formatting, persistence, error/badge display |
| `web/js/pipeline.js` | 432 | ~18 KB | Data pipeline (loading, resampling, Δt computation, geometry) |
| `web/js/circuitMap.js` | 168 | ~7.8 KB | Circuit map rendering (outline, heatmaps, legend, zoom arc) |
| `web/js/panels.js` | 264 | ~14 KB | **NEW** — Panel SVG rendering (`renderPanel`, `renderDtPanel`) |
| `web/js/constants.js` | 6 | ~0.4 KB | **NEW** — Shared SVG layout constants |
| `web/compare.html` | — | — | Single-page app (no build step, ESM imports from CDN) |

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

## What Changed in Step 8

### New Module: `web/js/panels.js`

Extracted panel rendering from `main.js`:

```javascript
export function renderPanel(def, bins, maxDist, sectorDists, zoomRange);
export function renderDtPanel(def, dtBins, maxDist, sectorDists, zoomRange, overlapRange);
```

### Fix: Contextual Y-Axis Scaling

**Before:** Y-axis range computed from ALL bin values (full lap), even when zoomed in.

**After:** Y-axis range computed from values **within the zoom range only**:
- `renderPanel()`: Collects values from `zoomStart` to `zoomEnd`
- `renderDtPanel()`: Collects values from intersection of overlap AND zoom ranges

This ensures zoomed-in sections show meaningful variation rather than being compressed.

### New Document: `RENDER_DESIGN.md`

Comprehensive rendering architecture document covering:
- Module structure and responsibilities
- SVG layout constants and coordinate system
- Panel rendering pipeline
- Circuit map rendering
- Zoom interaction mechanics
- Y-axis tick generation strategies
- Special cases and performance notes

### Changes to `main.js`

**Added imports:**
```javascript
import { renderPanel, renderDtPanel } from './panels.js';
import { SVG_W, PAD, PLOT_W } from './constants.js';
```

**Removed:** ~245 lines of panel rendering code (`renderPanel`, `renderDtPanel` functions).

**Remaining in `main.js`:**
- `renderAll()` — master orchestrator (~190 lines)
- Picker UI logic (`rebuildPickers`, `updateCompareBtn`, `parsePickerValue`)
- File loading orchestration (`loadFile`, `loadSidecar`, `loadDeltabestCsv`)
- Session list UI (`addSessionEntry`, `refreshSessionListBadges`)
- Cursor/tooltip logic (`updateCursorPosition`, `updateCursorDot`)
- Zoom interaction handlers (mousedown, mousemove, mouseup, dblclick, keydown)
- Drag-reorder handlers (F9)
- Lap colour picker handlers
- Debug hooks (`window.__resamplerDebug`, etc.)

---

## Learnings from Step 8

### 1. Parameter Passing for State-Dependent Functions

Confirmed the pattern from Step 7: pass state as parameters to rendering functions, not module-scope imports. This keeps modules pure and testable.

### 2. Contextual Y-Axis Requires Zoom-Aware Value Collection

The fix required changing **where** values are collected, not just **how** the range is computed. Both `renderPanel` and `renderDtPanel` now iterate over the zoom range when collecting values for `niceRange()`.

### 3. Δt Panel Has Two Constraints (Overlap + Zoom)

The Δt panel must respect both:
- **Overlap range:** Where both laps have real data (boundary clamp protection)
- **Zoom range:** What the user is currently viewing

Y-axis range is computed from the intersection: `max(overlapStart, zoomStart)` to `min(overlapEnd, zoomEnd)`.

---

## Step 9: Extract `ui.js`

### Functions to Extract

| Function | Lines in main.js | Description |
|----------|------------------|-------------|
| `rebuildPickers()` | ~40 lines | Populates session/ref pickers from store |
| `updateCompareBtn()` | ~5 lines | Enables/disables compare button |
| `parsePickerValue()` | ~6 lines | Parses `key::segIdx` format |
| `loadDeltabestCsv()` | ~60 lines | Parses TinyPedal CSV format |
| `loadSidecar()` | ~20 lines | Loads JSON sidecar metadata |
| `loadFile()` | ~50 lines | Main file loading orchestration |
| `refreshSessionListBadges()` | ~10 lines | Updates session list badges |
| `addSessionEntry()` | ~15 lines | Adds session entry to DOM |
| `updateCursorPosition()` | ~50 lines | Cursor line + tooltip on mousemove |
| `updateCursorDot()` | ~15 lines | Cursor dot on circuit map |
| Zoom handlers | ~80 lines | mousedown, mousemove, mouseup, dblclick, keydown |
| Drag-reorder handlers | ~60 lines | dragstart, dragover, drop, dragend, etc. |
| Lap colour handlers | ~20 lines | Colour picker input + reset |
| Event wiring | ~30 lines | Click handlers, picker change, map mode change |

**Total:** ~550-600 lines to extract

### Constants/State to Move or Share

| Item | Current Location | Recommendation |
|------|------------------|----------------|
| `plotArea`, `cursorLine`, `tooltip` | module-scope in `main.js` | Move to `ui.js`, export if needed |
| `state.dragging`, `state.dragStartX`, etc. | `appState.js` | Already in `appState.js` — keep there |
| `currentSessionBins`, `currentRefBins`, etc. | module-scope in `main.js` | Keep in `main.js` (render state) |
| `SVG_W`, `PAD`, `PLOT_W` | `constants.js` | Import in `ui.js` as needed |

### Dependencies

`ui.js` will import:
```javascript
import { store, pendingSidecars, state } from './appState.js';
import { storeKey, fileStem, formatDuration, lapStatusBadges, formatPickLabel,
         shortVehicle, shortSetup, showError, clearError, setBadge,
         persistZoom, LAP_COLOUR_DEFAULTS, persistLapColours } from './utils.js';
import { readColumns, buildSegments, annotateSegments, resample,
         smoothLapTime, smoothDt, computeKeepIndices, computeMedianFrameDistanceDelta,
         deriveSectorDistances } from './pipeline.js';
import { SVG_W, PAD, PLOT_W } from './constants.js';
import { renderAll } from './main.js';  // ⚠️ circular dependency risk!
```

### ⚠️ Circular Dependency Risk

**Problem:** `ui.js` needs to call `renderAll()` after file loads or zoom changes, but `renderAll` is in `main.js`. If `main.js` imports from `ui.js`, we have a cycle.

**Solutions:**

1. **Pass `renderAll` as a callback** (recommended):
   ```javascript
   // main.js
   import { initUI } from './ui.js';
   initUI(renderAll);  // Pass renderAll as parameter
   ```

2. **Export `renderAll` from a separate module** (cleaner but more refactoring):
   ```javascript
   // renderer.js
   export function renderAll(...) { ... }
   // main.js and ui.js both import from renderer.js
   ```

3. **Keep event wiring in `main.js`** (minimal extraction):
   Only extract the handler functions, not the `addEventListener` calls.

**Recommended:** Option 1 — pass `renderAll` as a callback to `initUI()`. This keeps the module structure simple and avoids creating a new file.

---

## Recommended Approach for Step 9

### Phase 1: Create `ui.js` with Pure Functions First

Start with functions that don't depend on module-scope state:
- `parsePickerValue()`
- `updateCompareBtn()`
- `addSessionEntry()`
- `refreshSessionListBadges()`

These can be extracted cleanly with no circular dependency risk.

### Phase 2: Extract File Loading Functions

- `loadDeltabestCsv()`
- `loadSidecar()`
- `loadFile()`

These call `rebuildPickers()` and `refreshSessionListBadges()`, so extract those first.

### Phase 3: Extract Picker Functions

- `rebuildPickers()`

This reads from `store` (imported from `appState.js`) and manipulates DOM.

### Phase 4: Extract Cursor/Tooltip Functions

- `updateCursorPosition()`
- `updateCursorDot()`

These read `currentSessionBins`, `currentRefBins`, `currentZoomRange`, etc. — which are module-scope in `main.js`. **Decision:** Pass these as parameters or keep these functions in `main.js`.

**Recommended:** Keep cursor/tooltip functions in `main.js` for now — they're tightly coupled to render state. Revisit in Step 10 or 11.

### Phase 5: Extract Zoom and Drag Handlers

These are event handlers that read/write `state` and call `renderAll`. Extract as functions, but keep `addEventListener` wiring in `main.js` (or pass handlers back to `main.js`).

### Phase 6: Create `initUI(renderAll)` Entry Point

Export a single `initUI(renderAll)` function that:
- Sets up all event listeners
- Returns any handlers that `main.js` needs to wire up

---

## Validation Checklist for Step 9

Before considering Step 9 complete:

- [ ] Run `npm run build` — verify no esbuild errors
- [ ] Run `npm test` — all 81 assertions must pass
- [ ] Open `dist/compare.html` in browser — verify:
  - File loading works (parquet, sidecar, CSV)
  - Pickers populate correctly
  - Compare button enables when both pickers selected
  - Cursor line and tooltip follow mouse
  - Tooltip shows correct values (dist, speed, throttle, brake, Δt, active flags)
  - Cursor dot moves on circuit map
  - Zoom interaction works (drag to zoom, dblclick/Esc to reset)
  - Panel drag-reorder works via grip handle
  - Lap colour pickers change trace colours
  - Reset buttons work (colours, panel order, zoom)
- [ ] Check console for "undefined" errors (scope issues)
- [ ] Verify no circular dependency errors in browser console

**Quick smoke test:**
```bash
npm run build && npm test
open dist/compare.html  # Manual verification
```

---

## Debug Tips

### Circular Dependency Error
```
ReferenceError: Cannot access 'renderAll' before initialization
```
**Fix:** Don't import `renderAll` directly. Pass it as a callback to `initUI()`.

### Undefined Module-Scope Variables
```
Cannot read properties of undefined (reading 'speed_kph')
```
**Fix:** If a function reads `currentSessionBins`, either:
1. Pass it as a parameter
2. Keep the function in `main.js`
3. Move the state to `appState.js` (if it's truly global)

### Event Handlers Not Firing
**Check:**
1. `addEventListener` is called after the DOM element exists
2. Handler function is correctly bound (not `undefined`)
3. Event delegation is set up correctly (for dynamic elements)

### Tooltip Not Updating
**Check:**
1. `updateCursorPosition` is called on `mousemove`
2. `currentSessionBins` is populated before hover
3. `plotArea` element exists when listener is attached

---

## Estimated Impact

| Metric | Before | After | Δ |
|--------|--------|-------|---|
| `main.js` lines | 1066 | ~500-600 | -450 to -550 |
| `ui.js` lines | — | ~550-600 | +550-600 |
| Total files | 7 | 8 | +1 |

**Reduction:** `main.js` reduced by ~45-50% (1066 → ~500-600 lines)

---

## Next Steps After Step 9

Depending on progress:
- **Step 10:** Extract `pickers.js` (~150 lines) — picker DOM projection, medium risk
- **Step 11:** Extract `dataTransforms.js` (~200 lines) — pure data parsing from file loading
- **Step 12:** Final cleanup — create `main.js` as thin entry point, update `compare.html`

**Ultimate goal:** `main.js` under 500 lines, with clear separation:
- `pipeline.js` — data loading/processing (done ✓)
- `circuitMap.js` — circuit map rendering (done ✓)
- `panels.js` — telemetry panel rendering (done ✓)
- `ui.js` — user interaction (event handlers, file loading) — Step 9
- `pickers.js` — picker/session-list DOM projection — Step 10
- `dataTransforms.js` — pure data parsing — Step 11
- `constants.js` — shared constants (done ✓)
- `appState.js` — global state (done ✓)
- `utils.js` — helpers (done ✓)
- `main.js` — app entry point, `renderAll` orchestration, debug hooks

---

## Appendix: File Sizes After Step 8

```
web/js/main.js        1066 lines  (~45 KB)
web/js/appState.js      59 lines  (~2.6 KB)
web/js/utils.js        129 lines  (~5 KB)
web/js/pipeline.js     432 lines  (~18 KB)
web/js/circuitMap.js   168 lines  (~7.8 KB)
web/js/panels.js       264 lines  (~14 KB)
web/js/constants.js      6 lines  (~0.4 KB)
──────────────────────────────────────────
Total:                2124 lines  (~93 KB)
```

**Reduction from original:** `main.js` reduced from 1869 → 1066 lines (-43%)

---

## Notes

- **Step 9 is highest risk** due to event handler scope rules and circular dependency potential
- **Cursor/tooltip functions** may stay in `main.js` — they're tightly coupled to render state
- **Pass `renderAll` as callback** to avoid circular imports
- **Keep `addEventListener` wiring** in `main.js` or have `initUI` return handlers
- **Test frequently** — extract a few functions, run tests, verify in browser, repeat
- **No behavioural changes** — pure extraction refactor
