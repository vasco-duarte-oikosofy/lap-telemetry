# Web Refactor — Step 10 Handoff

**Date:** 2026-05-13  
**Status:** Step 9 complete (ui.js extracted, all 81 tests passing)  
**Next:** Step 10 — Extract `pickers.js` (picker/session-list DOM projection)

---

## Current State

### Files
| File | Lines | Size | Role |
|------|-------|------|------|
| `web/js/main.js` | 623 | ~27 KB | App entry point, `renderAll`, cursor/tooltip, zoom handlers |
| `web/js/ui.js` | 497 | ~21 KB | **NEW** — UI interaction (event handlers, file loading) |
| `web/js/appState.js` | 59 | ~2.6 KB | Global state (`store`, `panelOrder`, map mode) |
| `web/js/utils.js` | 129 | ~5 KB | String helpers, formatting, persistence, error/badge display |
| `web/js/pipeline.js` | 432 | ~18 KB | Data pipeline (loading, resampling, Δt computation, geometry) |
| `web/js/circuitMap.js` | 168 | ~7.8 KB | Circuit map rendering (outline, heatmaps, legend, zoom arc) |
| `web/js/panels.js` | 283 | ~14 KB | Panel SVG rendering (`renderPanel`, `renderDtPanel`) |
| `web/js/constants.js` | 6 | ~0.4 KB | Shared SVG layout constants |
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

## What Changed in Step 9

### New Module: `web/js/ui.js`

Extracted ~550 lines of UI interaction code from `main.js`:

```javascript
export function rebuildPickers();
export function updateCompareBtn();
export function parsePickerValue(val);
export async function loadFile(file, renderAll);
export function refreshSessionListBadges();
export function addSessionEntry(name, key, statusText);
export function disarmAllPanels();
export function setupPanelDragHandlers(renderAll);
export function initUI(renderAll);  // Entry point
```

### Fix: Parallel File Loading

**Bug discovered:** Changed `Promise.all(files.map(loadFile))` to sequential `for...await`, which broke sidecar attachment timing when parquet+JSON are loaded together.

**Fix:** Restored parallel loading:
```javascript
await Promise.all(files.map(f => loadFile(f, renderAll)));
```

### Pattern: Callback Parameter for `renderAll`

To avoid circular dependencies, `initUI()` accepts `renderAll` as a callback:
```javascript
// main.js
import { initUI } from './ui.js';
initUI(renderAll);
```

This pattern should be reused for Step 10.

### Functions Kept in `main.js`

Cursor/tooltip and zoom handlers stayed in `main.js` because they read module-scope render state:
- `updateCursorPosition()` — reads `currentSessionBins`, `currentRefBins`, `currentZoomRange`, `currentOverlapRange`
- `updateCursorDot()` — reads `currentTrackX`, `currentTrackZ`, `trackTransform`
- Zoom event handlers — read/write `currentZoomRange`, call `renderAll`
- Map-mode handler — calls `renderCircuitMap` with current render state

---

## Learnings from Step 9

### 1. Parallel File Loading is Critical

The sidecar attachment logic depends on parquet and JSON loading in parallel:
```javascript
// loadSidecar() checks if parquet already loaded for this stem
// If parquet loads first, sidecar attaches immediately
// If sidecar loads first, it goes into pendingSidecars
// Either way, rebuildPickers() must fire after both are ready
```

**Lesson:** Keep `Promise.all()` for multi-file loads. Sequential loading breaks the race-condition-tolerant design.

### 2. Callback Parameters Beat Dynamic Imports

Initially tried dynamic `import()` inside event handlers to avoid circular deps:
```javascript
// BAD: async, hard to test, delays execution
import('./appState.js').then(({ panelOrder }) => { ... });
```

**Better:** Pass what you need as parameters:
```javascript
// GOOD: synchronous, testable, clear dependencies
export function initUI(renderAll) { ... }
export function setupPanelDragHandlers(renderAll) { ... }
```

### 3. Module-Scope State Dictates Module Boundaries

Functions that read `currentSessionBins`, `currentZoomRange`, etc. must stay in `main.js` **or** those values must be passed as parameters.

**Decision:** Keep cursor/tooltip/zoom in `main.js` for now — they're tightly coupled to render state and called on every mousemove. Passing 5+ parameters on every event would be awkward.

**Future:** If `main.js` is still too large after Steps 10-11, consider moving render state to `appState.js` (but this risks bloating the global state module).

### 4. Import Order Matters for esbuild

esbuild processes imports top-to-bottom. Keep CDN imports last:
```javascript
// Internal modules first
import { ... } from './ui.js';
import { ... } from './panels.js';
// CDN imports last
import { parquetRead } from 'https://...';
```

### 5. Test After Each Extraction

Step 9 had a regression (heatmap tests failed) because the map-mode handler was extracted but didn't have access to `renderCircuitMap`. Caught immediately by running `npm test`.

**Lesson:** Build + test after every 2-3 function extractions, not at the end.

---

## Step 10: Extract `pickers.js`

### Functions to Extract

| Function | Lines in main.js | Description |
|----------|------------------|-------------|
| `rebuildPickers()` | ~60 lines | Populates session/ref pickers from store |
| `updateCompareBtn()` | ~5 lines | Enables/disables compare button |
| `parsePickerValue()` | ~6 lines | Parses `key::segIdx` format |
| `addSessionEntry()` | ~15 lines | Adds session entry to DOM |
| `refreshSessionListBadges()` | ~10 lines | Updates session list badges |

**Total:** ~95-100 lines to extract

### Dependencies

`pickers.js` will import:
```javascript
import { store } from './appState.js';
import { storeKey, fileStem, formatDuration, lapStatusBadges, formatPickLabel,
         shortVehicle, shortSetup, setBadge } from './utils.js';
import { rebuildPickers, updateCompareBtn, parsePickerValue,
         addSessionEntry, refreshSessionListBadges } from './pickers.js';
```

### Export Strategy

These functions are currently:
1. **Exported from `ui.js`** (Step 9)
2. **Imported by `main.js`**

For Step 10, `ui.js` will re-export from `pickers.js`:
```javascript
// pickers.js
export function rebuildPickers() { ... }
export function updateCompareBtn() { ... }
// etc.

// ui.js
export { rebuildPickers, updateCompareBtn, parsePickerValue,
         addSessionEntry, refreshSessionListBadges } from './pickers.js';

// main.js — no changes needed!
import { initUI, rebuildPickers, ... } from './ui.js';
```

This keeps `main.js` unchanged and makes the extraction transparent.

### No Circular Dependency Risk

These functions are pure DOM manipulation + store reads. They don't call `renderAll` directly (only `updateCompareBtn` is called by picker change handlers in `ui.js`).

---

## Recommended Approach for Step 10

### Phase 1: Create `pickers.js` with Pure Functions

```javascript
// web/js/pickers.js
import { store } from './appState.js';
import { storeKey, fileStem, formatDuration, lapStatusBadges, formatPickLabel,
         shortVehicle, shortSetup, setBadge } from './utils.js';

export function parsePickerValue(val) { ... }
export function updateCompareBtn() { ... }
export function addSessionEntry(name, key, statusText) { ... }
export function refreshSessionListBadges() { ... }
export function rebuildPickers() { ... }
```

### Phase 2: Re-export from `ui.js`

```javascript
// ui.js — replace function bodies with re-exports
export { rebuildPickers, updateCompareBtn, parsePickerValue,
         addSessionEntry, refreshSessionListBadges } from './pickers.js';
```

### Phase 3: Remove from `ui.js`

Delete the function bodies from `ui.js` (they're now in `pickers.js`).

### Phase 4: Verify

```bash
npm run build && npm test
```

No changes to `main.js` should be needed.

---

## Validation Checklist for Step 10

Before considering Step 10 complete:

- [ ] Run `npm run build` — verify no esbuild errors
- [ ] Run `npm test` — all 81 assertions must pass
- [ ] Open `dist/compare.html` in browser — verify:
  - File loading works (parquet, sidecar, CSV)
  - Pickers populate correctly with optgroups
  - Picker labels show vehicle name + setup (e.g., "JMW #66:ELMS (GT3_296_Balanced_Barcelona)")
  - Compare button enables when both pickers selected
  - Session list badges show row count + laps + vehicle
  - Remove button works (removes from store, rebuilds pickers)
- [ ] Check `ui.js` line count reduced by ~100 lines
- [ ] Verify `pickers.js` has no CDN imports (pure DOM + store)

**Quick smoke test:**
```bash
npm run build && npm test
open dist/compare.html  # Manual verification
```

---

## Debug Tips

### Picker Labels Empty or Wrong Format
**Check:**
1. `formatPickLabel()` is imported from `utils.js`
2. `entry.sidecar` is populated (check `loadFile` attaches it)
3. `shortVehicle()` and `shortSetup()` are working (regex tests)

### Compare Button Not Enabling
**Check:**
1. `updateCompareBtn()` is called after `rebuildPickers()`
2. Picker values are non-empty (check `<option value="...">` format)
3. `parsePickerValue()` returns `{ key, segIdx }` for valid input

### Session List Badge Not Updating
**Check:**
1. `setBadge()` is called with correct element ID (`badge-${CSS.escape(key)}`)
2. `refreshSessionListBadges()` iterates over `store.entries()`
3. `entry.sidecar.vehicle_name` exists for the metadata

### esbuild Import Errors
**Check:**
1. All imports use `.js` extension
2. No circular imports (`pickers.js` → `ui.js` → `pickers.js`)
3. Re-exports use correct syntax: `export { x } from './y.js';`

---

## Estimated Impact

| Metric | Before | After | Δ |
|--------|--------|-------|---|
| `ui.js` lines | 497 | ~400 | -97 |
| `pickers.js` lines | — | ~100 | +100 |
| `main.js` lines | 623 | 623 | 0 |
| Total files | 8 | 9 | +1 |

**Reduction:** `ui.js` reduced by ~20% (497 → ~400 lines)

---

## Next Steps After Step 10

Depending on progress:
- **Step 11:** Extract `dataTransforms.js` (~200 lines) — pure data parsing from file loading (`loadDeltabestCsv` helper logic)
- **Step 12:** Extract cursor/tooltip to `cursor.js` (if `main.js` still >500 lines)
- **Step 13:** Final cleanup — create `main.js` as thin entry point, update `compare.html`

**Ultimate goal:** `main.js` under 500 lines, with clear separation:
- `pipeline.js` — data loading/processing (done ✓)
- `circuitMap.js` — circuit map rendering (done ✓)
- `panels.js` — telemetry panel rendering (done ✓)
- `pickers.js` — picker/session-list DOM projection — Step 10
- `ui.js` — user interaction (event handlers, file loading) — Step 9 ✓
- `cursor.js` — cursor/tooltip/zoom interaction — Step 12?
- `dataTransforms.js` — pure data parsing — Step 11?
- `constants.js` — shared constants (done ✓)
- `appState.js` — global state (done ✓)
- `utils.js` — helpers (done ✓)
- `main.js` — app entry point, `renderAll` orchestration, debug hooks

---

## Appendix: File Sizes After Step 9

```
web/js/main.js         623 lines  (~27 KB)
web/js/ui.js           497 lines  (~21 KB)
web/js/pipeline.js     432 lines  (~18 KB)
web/js/panels.js       283 lines  (~14 KB)
web/js/utils.js        129 lines  (~5 KB)
web/js/circuitMap.js   168 lines  (~7.8 KB)
web/js/appState.js      59 lines  (~2.6 KB)
web/js/constants.js      6 lines  (~0.4 KB)
──────────────────────────────────────────
Total:                2197 lines  (~96 KB)
```

**Reduction from original:** `main.js` reduced from 1869 → 623 lines (-67%)

---

## Notes

- **Step 10 is low risk** — pure DOM manipulation, no render state dependencies
- **Re-export pattern** keeps `main.js` unchanged (no ripple effect)
- **Test after extraction** — verify picker labels, compare button, session badges
- **No behavioural changes** — pure extraction refactor
- **Parallel file loading** — keep `Promise.all()` in `loadFile()`
