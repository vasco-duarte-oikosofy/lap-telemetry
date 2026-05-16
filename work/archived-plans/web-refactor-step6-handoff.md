# Web Refactor — Step 6 Handoff

**Date:** 2026-05-13  
**Status:** Step 5 complete (utils.js extracted, all tests passing)  
**Next:** Extract data pipeline module (`pipeline.js`)

---

## Current State

### Files
| File | Size | Role |
|------|------|------|
| `web/js/main.js` | ~81 KB, 1869 lines | App entry point, DOM rendering, event handlers |
| `web/js/appState.js` | 2.6 KB | Global state (`state`, `getCurrentMapMode`, `setCurrentMapMode`, panel order persistence) |
| `web/js/utils.js` | 5 KB | String helpers, formatting, persistence, error/badge display |
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

## Known Issues / Gotchas

### ES Modules Require HTTP(S)

`web/compare.html` uses `<script type="module" src="js/main.js">`. **This does not work via `file://`** due to browser CORS restrictions on ES modules.

**Symptoms:**
- Console errors: "Cross-Origin Request Blocked" or "Module source URI is not allowed"
- Button clicks do nothing (JavaScript never loaded)
- Page renders but is non-functional

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
  const d2 = Math.min(state.maxDist, ...);  // OK
  persistZoom(currentZoomRange, maxDist);   // undefined!
});

// ✅ Correct - use state.maxDist
plotArea.addEventListener('mouseup', e => {
  const d2 = Math.min(state.maxDist, ...);
  persistZoom(currentZoomRange, state.maxDist);  // OK
});
```

---

## Goal for Step 6

Extract the **data pipeline** functions from `main.js` into a new `web/js/pipeline.js` module. These are pure computation functions that:
- Load and parse Parquet files
- Build lap segments from `lap_number` column
- Annotate segments with rolling/partial flags
- Resample telemetry to 1 m distance bins
- Compute Δt between session and reference laps
- Smooth gear/Δt signals
- Derive sector distances from sidecar

**Target:** Reduce `main.js` by ~400 lines, improve testability of data logic.

---

## Functions to Extract

### From `main.js` (approximate line numbers)

| Function | Lines | Description | Dependencies | Scope Notes |
|----------|-------|-------------|--------------|-------------|
| `fileToAsyncBuffer` | 112–119 | FileReader wrapper | None | Pure helper — OK to extract |
| `readColumns` | 121–154 | hyparquet column reader | `fileToAsyncBuffer` | Called from `loadFile` — OK to extract |
| `buildSegments` | 156–186 | Group rows by `lap_number` | None | Pure function — OK to extract |
| `annotateSegments` | 191–244 | Mark rolling/partial laps | `PARTIAL_*` constants | Called from `loadFile` — OK to extract |
| `interpAt` | 246–257 | Linear interpolation helper | None | Called by `resample` — OK to extract |
| `resample` | 259–277 | Distance-aligned resampler | `interpAt` | Called from `renderAll` — OK to extract |
| `computeDeltaT` | 279–291 | Session vs ref lap time diff | None | Pure function — OK to extract |
| `computeKeepIndices` | 293–311 | Δt overlap window | None | Pure function — OK to extract |
| `smoothLapTime` | 313–340 | Δt smoothing (rolling median) | None | Pure function — OK to extract |
| `smoothDt` | 342–359 | Δt smoothing with radius | None | Pure function — OK to extract |
| `smoothGear` | 361–379 | Gear signal cleanup | None | Pure function — OK to extract |
| `deriveSectorDistances` | 381–428 | S1/S2 distances from sidecar | None | Called from `renderAll` — OK to extract |
| `niceRange` | 430–437 | Y-axis range computation | None | Called from render functions — OK to extract |
| `buildPolylinePts` | 439–451 | SVG polyline builder | None | Pure helper — OK to extract |
| `computeTrackBounds` | 453–463 | Circuit map bounding box | None | Pure helper — OK to extract |
| `buildTrackTransform` | 465–477 | Map coordinate transform | `computeTrackBounds` | Pure helper — OK to extract |
| `buildTrackPolylinePts` | 479–487 | Track outline polyline | `buildTrackTransform` | Pure helper — OK to extract |
| `computeMedianFrameDistanceDelta` | 489–504 | Coarse-data detection | None | Pure helper — OK to extract |
| `computeNiceYTicks` | 506–534 | Δt/Slip tick generation | `niceRange` | Pure helper — OK to extract |

### Constants to Move

```javascript
// From main.js ~line 188–191
const PARTIAL_DIST_FRAC = 0.95;
const PARTIAL_DUR_FRAC  = 0.5;
const ROLLING_DIST_M    = 50;
```

---

## New Module: `web/js/pipeline.js`

### Exports

```javascript
// Constants
export const PARTIAL_DIST_FRAC;
export const PARTIAL_DUR_FRAC;
export const ROLLING_DIST_M;

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

---

## Changes to `main.js`

### Add Import

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

### Remove

Delete the extracted functions and constants from `main.js`.

### Update Call Sites

All call sites remain unchanged — function names and signatures are preserved.

---

## Extraction Guidelines

### Safe to Extract
- **Pure functions** with no DOM access or global state
- Functions that only use their parameters and imported constants
- Helper functions called only from other extractable functions

### Keep in main.js
- **Event handlers** (mouse, keyboard, click listeners)
- Functions that access DOM elements directly
- Functions that read/write `state` object properties
- Functions that use `currentZoomRange`, `currentSessionBins`, etc.

### Watch Out For
- Functions called from event handlers must not rely on closure over local variables
- If a function uses `maxDist`, `zoomRange`, etc., ensure these are on `state` or passed as parameters
- Test extraction by running `npm run build` — esbuild will catch import errors

---

## Validation Checklist

Before considering Step 6 complete:

- [ ] Run `npm run build` — verify no esbuild errors
- [ ] Run `npm test` — all 81 assertions must pass
- [ ] Open `dist/compare.html` in browser — verify zoom drag works
- [ ] Check console for "undefined" errors (scope issues)
- [ ] Verify file picker button works (when served via HTTP)

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
3. Common culprits: `maxDist`, `zoomRange`, `currentRenderParams`

### Module Import Errors
If `npm run build` fails with import errors:
1. Verify all exports in `pipeline.js` are named correctly
2. Check import statement in `main.js` matches exports exactly
3. Ensure no circular dependencies (pipeline.js should not import main.js)

### Testing File Picker
The "+ Load parquet" button requires HTTP:
```bash
# Option 1: Use dist/ (bundled, works via file://)
open dist/compare.html

# Option 2: Serve web/ via HTTP
python3 -m http.server 8000
# Then open http://localhost:8000
```

---

## Acceptance Criteria

- [ ] `web/js/pipeline.js` created with all exports above
- [ ] `main.js` imports from `pipeline.js`, extracted code removed
- [ ] `npm run build` produces `dist/compare.html` without errors
- [ ] All tests pass: `npm test` (M5, M6, F1F2, Extras — 81 assertions)
- [ ] No console errors in browser during test runs

---

## Notes

- **No behavioural changes** — this is a pure extraction refactor
- `pipeline.js` functions are **pure** (no DOM access, no global state)
- Keep `COLUMNS` constant in `main.js` (used by UI, not pipeline)
- Keep `PANEL_DEFS`, `HEATMAP_RAMPS`, `HEATMAP_CHANNELS` in `main.js` (rendering concerns)
- Keep `renderAll`, `renderPanel`, `renderDtPanel` in `main.js` (DOM rendering)
- Keep `rebuildPickers`, event handlers in `main.js` (UI logic)

---

## Next Steps After Step 6

**Step 7 candidates** (TBD):
- Extract `panels.js` — `renderPanel`, `renderDtPanel`, panel-specific SVG logic
- Extract `circuitMap.js` — `renderCircuitMap`, `renderHeatmapSegments`, `renderMapLegend`, `updateZoomArc`
- Extract `ui.js` — picker rebuild, compare button, drag-and-drop handlers

**Caution:** Event handlers in `ui.js` must use `state` object, not closure over local variables. Review the "Known Issues / Gotchas" section before extracting.

---

## Appendix: Recent Bug Fixes (2026-05-13)

### Bug 1: Zoom Not Working in dist/compare.html
**Root cause:** Event handler used `maxDist` (local to `renderAll`) instead of `state.maxDist`.  
**Fix:** Changed line 1632 in `web/js/main.js`:
```javascript
// Before (broken)
persistZoom(currentZoomRange, maxDist);

// After (fixed)
persistZoom(currentZoomRange, state.maxDist);
```

### Bug 2: File Picker Not Opening in web/compare.html
**Root cause:** Not a code bug — ES modules don't load via `file://` protocol.  
**Workaround:** Use `dist/compare.html` or serve via HTTP.

### Test Suites Added
- `scripts/test_zoom_bug.js` — Verifies drag-to-zoom in dist/compare.html
- `scripts/test_file_picker_bug.js` — Verifies file picker works via HTTP
