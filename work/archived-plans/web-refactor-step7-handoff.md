# Web Refactor — Step 7 Handoff

**Date:** 2026-05-13  
**Status:** Step 6 complete (pipeline.js extracted, all tests passing)  
**Next:** TBD — candidates: `panels.js`, `circuitMap.js`, or `ui.js`

---

## Current State

### Files
| File | Size | Role |
|------|------|------|
| `web/js/main.js` | ~63 KB, 1437 lines | App entry point, DOM rendering, event handlers |
| `web/js/appState.js` | 2.6 KB | Global state (`state`, `getCurrentMapMode`, `setCurrentMapMode`, panel order persistence) |
| `web/js/utils.js` | 5 KB | String helpers, formatting, persistence, error/badge display |
| `web/js/pipeline.js` | 18 KB, 432 lines | **NEW** — pure data pipeline (loading, resampling, Δt computation, geometry helpers) |
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

## What Changed in Step 6

### New Module: `web/js/pipeline.js`

Extracted 19 pure functions and 3 constants from `main.js`:

```javascript
// Constants
export const PARTIAL_DIST_FRAC;  // 0.95
export const PARTIAL_DUR_FRAC;   // 0.5
export const ROLLING_DIST_M;     // 50

// File I/O
export async function fileToAsyncBuffer(file);
export async function readColumns(file, columns);

// Segment building
export function buildSegments(lapNumbers);
export function annotateSegments(segments, distances, lapTimes);

// Resampling & interpolation
export function interpAt(xs, ys, x);
export function resample(distances, values, maxDist);

// Δt computation
export function computeDeltaT(sessionLapTime, refLapTime);
export function computeKeepIndices(lapTime, lapDist, start, end, trackLen);
export function smoothLapTime(lapTime, indices);
export function smoothDt(dt, maxRadius = 20);

// Signal processing
export function smoothGear(gear, indices, maxNeutralRun = 5);

// Sector helpers
export function deriveSectorDistances(entry, segIdx);

// Geometry helpers
export function niceRange(arr, yFixed, margin = 0.05);
export function buildPolylinePts(xs, ys, toX, toY, step = false);
export function computeTrackBounds(trackX, trackZ);
export function buildTrackTransform(bounds);
export function buildTrackPolylinePts(trackX, trackZ, toMapX, toMapZ);

// Diagnostics
export function computeMedianFrameDistanceDelta(distances);
export function computeNiceYTicks(yMin, yMax, plotH, niceSteps);
```

### Changes to `main.js`

**Added import:**
```javascript
import {
  fileToAsyncBuffer, readColumns, buildSegments, annotateSegments,
  interpAt, resample, computeDeltaT, computeKeepIndices, smoothLapTime,
  smoothDt, smoothGear, deriveSectorDistances, niceRange, buildPolylinePts,
  computeTrackBounds, buildTrackTransform, buildTrackPolylinePts,
  computeMedianFrameDistanceDelta, computeNiceYTicks,
  PARTIAL_DIST_FRAC, PARTIAL_DUR_FRAC, ROLLING_DIST_M
} from './pipeline.js';
```

**Removed:** ~432 lines of pure functions (lines 112–558 in original).

**Remaining in `main.js`:**
- `renderPanel`, `renderDtPanel` — SVG panel rendering (DOM access)
- `renderCircuitMap`, `renderHeatmapSegments`, `renderMapLegend`, `updateZoomArc` — circuit map rendering
- `rebuildPickers`, `updateCompareBtn`, `parsePickerValue` — picker UI logic
- `loadFile`, `loadSidecar`, `loadDeltabestCsv` — file loading orchestration
- `addSessionEntry`, `refreshSessionListBadges` — session list UI
- `updateCursorPosition`, `updateCursorDot` — cursor/tooltip logic
- All event handlers (mouse, keyboard, drag-and-drop)
- Debug hooks (`window.__resamplerDebug`, `window.__dtDebug`, etc.)

---

## Learnings from Step 6

### 1. Import Order Matters for Readability

Initial extraction placed the `pipeline.js` import before the CDN imports, which looked odd. Final order:
```javascript
// ── CDN imports ────────────────────────────────────────────────────────────
import { parquetRead, parquetMetadataAsync } from '...';
import { compressors } from '...';

// ── Application state ─────────────────────────────────────────────────────────
import { store, ... } from './appState.js';

// ── Utility helpers ────────────────────────────────────────────────────────────
import { storeKey, ... } from './utils.js';

// ── Data pipeline ──────────────────────────────────────────────────────────────
import { ... } from './pipeline.js';
```

**Lesson:** Keep CDN/external imports first, then local modules grouped by concern.

### 2. `edit` Tool Requires Exact Matches

The `edit` tool's `oldText` must match **exactly** including whitespace. When removing large blocks:
- Use `read` with offset/limit to get exact text
- Verify boundaries with `grep -n` for section markers
- Merge overlapping edits into one call

**Lesson:** For large deletions, read the file first to confirm exact boundaries.

### 3. Pipeline.js Uses Dynamic Imports for hyparquet

Since `pipeline.js` is a local module (not inlined in the HTML), it cannot rely on top-level CDN imports from `main.js`. The `readColumns` function uses dynamic imports:

```javascript
const { parquetMetadataAsync } = await import('https://cdn.jsdelivr.net/npm/hyparquet@1/+esm');
const { parquetRead } = await import('https://cdn.jsdelivr.net/npm/hyparquet@1/+esm');
const { compressors } = await import('https://cdn.jsdelivr.net/npm/hyparquet-compressors@1/+esm');
```

**Lesson:** Extracted modules that need CDN dependencies must import them locally.

### 4. No Behavioral Changes = Easy Validation

Because Step 6 was a pure extraction (no logic changes), validation was straightforward:
- `npm run build` succeeds → imports are correct
- `npm test` passes → behavior unchanged

**Lesson:** Pure extraction refactors are low-risk; test failures would indicate import/signature errors only.

---

## Known Issues / Gotchas

### ES Modules Require HTTP(S)

`web/compare.html` uses `<script type="module" src="js/main.js">`. **This does not work via `file://`** due to browser CORS restrictions on ES modules.

**Symptoms:**
- Console errors: "Cross-Origin Request Blocked" or "Module source URI is not allowed"
- Button clicks do nothing (JavaScript never loaded)

**Solutions:**
1. Use `dist/compare.html` — bundled single file, works via `file://`
2. Serve `web/` via HTTP: `python3 -m http.server 8000` or any static server

**Test runs must use HTTP** — the test server (`scripts/lib/test-server.js`) handles this correctly.

### Event Handler Scope Rules

Event handlers (e.g., `plotArea.addEventListener('mouseup', ...)`) **cannot access local variables** from functions like `renderAll()`. They must use:
- Global/module-scope variables (e.g., `state.maxDist`, `currentZoomRange`)
- Properties on `state` object for values that change per-render

**Common mistake:** Using `maxDist` (local to `renderAll`) in event handlers → `undefined` at runtime.

**Correct pattern:**
```javascript
// ❌ Wrong - maxDist is local to renderAll()
plotArea.addEventListener('mouseup', e => {
  persistZoom(currentZoomRange, maxDist);   // undefined!
});

// ✅ Correct - use state.maxDist
plotArea.addEventListener('mouseup', e => {
  persistZoom(currentZoomRange, state.maxDist);  // OK
});
```

---

## Step 7 Candidates

### Option A: Extract `panels.js` (~400 lines)

**Functions to extract:**
- `renderPanel(def, bins, maxDist, sectorDists, zoomRange)` — renders all non-Δt panels
- `renderDtPanel(def, dtBins, maxDist, sectorDists, zoomRange, overlapRange)` — renders Δt panel

**Constants to move:**
- `HEATMAP_RAMPS` — colour ramps for speed/brake/throttle heatmaps
- `HEATMAP_CHANNELS` — channel mapping for heatmaps

**Considerations:**
- These functions access DOM (`document.getElementById('panels')`)
- Would need to pass `state` or DOM references as parameters
- Or keep DOM manipulation in `main.js` and extract only SVG generation

**Estimated reduction:** ~250–300 lines from `main.js`

---

### Option B: Extract `circuitMap.js` (~200 lines)

**Functions to extract:**
- `renderCircuitMap()` — main circuit map renderer
- `renderHeatmapSegments(mode)` — heatmap segment generation
- `renderMapLegend()` — legend rendering
- `updateZoomArc()` — zoom indicator arc on map

**Constants to move:**
- `MAP_SIZE` (250)
- `MAP_PAD` (20)

**Considerations:**
- Functions access DOM elements directly (`document.getElementById('track-outline')`, etc.)
- Would need to either:
  - Pass DOM refs as parameters, or
  - Keep DOM access in `main.js` and extract pure SVG generation

**Estimated reduction:** ~150–180 lines from `main.js`

---

### Option C: Extract `ui.js` (~300 lines)

**Functions to extract:**
- `rebuildPickers()` — populate session/ref pickers
- `updateCompareBtn()` — enable/disable compare button
- `parsePickerValue(val)` — parse picker value format
- `loadFile`, `loadSidecar`, `loadDeltabestCsv` — file loading orchestration
- `addSessionEntry`, `refreshSessionListBadges` — session list UI
- `updateCursorPosition`, `updateCursorDot` — cursor/tooltip logic
- All event handlers (mouse, keyboard, drag-and-drop)

**Considerations:**
- **High coupling to `state` object** — all event handlers read/write `state`
- **High coupling to DOM** — direct element access throughout
- Would need to pass `state` and DOM refs as parameters, or use a module-scoped reference
- Drag-and-drop handlers use `state.dragId` — must ensure scope is correct

**Estimated reduction:** ~350–400 lines from `main.js`

**Risk:** Highest — event handler scope issues could break zoom, tooltip, or drag-reorder

---

## Recommended Approach for Step 7

**Start with Option B (`circuitMap.js`)** — lowest risk:
- Fewer functions (4 vs 10+)
- Clear boundaries (circuit map is self-contained)
- Less coupling to `state` (mostly reads `currentTrackX`, `currentTrackZ`, `trackTransform`, `currentZoomRange`)
- Can pass DOM refs as parameters to keep module pure

**Defer Option C (`ui.js`)** — highest risk due to event handler scope rules. Review the "Known Issues / Gotchas" section carefully before attempting.

---

## Validation Checklist for Step 7

Before considering Step 7 complete:

- [ ] Run `npm run build` — verify no esbuild errors
- [ ] Run `npm test` — all 81 assertions must pass
- [ ] Open `dist/compare.html` in browser — verify:
  - Circuit map renders (outline + heatmap modes)
  - Cursor dot tracks mouse on map
  - Zoom arc shows when zoomed
  - Legend updates with mode change
- [ ] Check console for "undefined" errors (scope issues)

**Quick smoke test:**
```bash
npm run build && npm test
open dist/compare.html  # Manual verification
```

---

## Debug Tips

### Scope Issues in Event Handlers
If zoom/click interactions stop working after refactoring:
1. Check browser console for `undefined` errors
2. Search event handlers for variables that should be `state.xxx`
3. Common culprits: `currentTrackX`, `currentTrackZ`, `trackTransform`, `currentZoomRange`

### Module Import Errors
If `npm run build` fails with import errors:
1. Verify all exports in new module are named correctly
2. Check import statement in `main.js` matches exports exactly
3. Ensure no circular dependencies

### Circuit Map Not Rendering
1. Verify `MAP_SIZE` and `MAP_PAD` constants are accessible (move to new module or pass as params)
2. Check that `currentTrackX`/`currentTrackZ` are passed correctly from `renderAll`
3. Verify SVG element IDs match (`track-outline`, `track-segments`, `circuit-map-panel`)

---

## Appendix: File Sizes After Step 6

```
web/js/main.js       1437 lines  (~63 KB)
web/js/appState.js     75 lines  (~2.6 KB)
web/js/utils.js       150 lines  (~5 KB)
web/js/pipeline.js    432 lines  (~18 KB)
─────────────────────────────────────────
Total:               2094 lines  (~88 KB)
```

**Reduction from original:** `main.js` reduced from 1869 → 1437 lines (-23%)

---

## Notes

- **No behavioural changes in Step 6** — pure extraction refactor
- `pipeline.js` functions are **pure** (no DOM access, no global state)
- `pipeline.js` uses dynamic imports for hyparquet (CDN dependencies)
- Keep `COLUMNS` constant in `main.js` (used by UI, not pipeline)
- Keep `PANEL_DEFS` in `main.js` (rendering concern)
- Keep `renderAll` in `main.js` (orchestrates across modules)

---

## Next Steps After Step 7

Depending on Step 7 choice:
- If `circuitMap.js`: consider `panels.js` next (medium risk)
- If `panels.js`: consider `circuitMap.js` next (lower risk)
- Save `ui.js` for last (highest risk — event handlers, state coupling)

**Ultimate goal:** `main.js` under 500 lines, with clear separation:
- `pipeline.js` — data loading/processing (done ✓)
- `circuitMap.js` — circuit map rendering
- `panels.js` — telemetry panel rendering
- `ui.js` — user interaction (pickers, file loading, drag-reorder)
- `main.js` — app entry point, `renderAll` orchestration
