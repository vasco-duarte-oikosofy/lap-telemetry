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

| Function | Lines | Description | Dependencies |
|----------|-------|-------------|--------------|
| `fileToAsyncBuffer` | 112–119 | FileReader wrapper | None |
| `readColumns` | 121–154 | hyparquet column reader | `fileToAsyncBuffer` |
| `buildSegments` | 156–186 | Group rows by `lap_number` | None |
| `annotateSegments` | 191–244 | Mark rolling/partial laps | `PARTIAL_*` constants |
| `interpAt` | 246–257 | Linear interpolation helper | None |
| `resample` | 259–277 | Distance-aligned resampler | `interpAt` |
| `computeDeltaT` | 279–291 | Session vs ref lap time diff | None |
| `computeKeepIndices` | 293–311 | Δt overlap window | None |
| `smoothLapTime` | 313–340 | Δt smoothing (rolling median) | None |
| `smoothDt` | 342–359 | Δt smoothing with radius | None |
| `smoothGear` | 361–379 | Gear signal cleanup | None |
| `deriveSectorDistances` | 381–428 | S1/S2 distances from sidecar | None |
| `niceRange` | 430–437 | Y-axis range computation | None |
| `buildPolylinePts` | 439–451 | SVG polyline builder | None |
| `computeTrackBounds` | 453–463 | Circuit map bounding box | None |
| `buildTrackTransform` | 465–477 | Map coordinate transform | `computeTrackBounds` |
| `buildTrackPolylinePts` | 479–487 | Track outline polyline | `buildTrackTransform` |
| `computeMedianFrameDistanceDelta` | 489–504 | Coarse-data detection | None |
| `computeNiceYTicks` | 506–534 | Δt/Slip tick generation | `niceRange` |

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
