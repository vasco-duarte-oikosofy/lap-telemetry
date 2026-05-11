# Web Viewer Refactoring Plan

Refactor the monolithic `web/compare.html` (2,208 lines) into a clean
multi-file ESM architecture. Zero behaviour change — every panel, tooltip,
zoom interaction, colour picker, CSV ingest, and Playwright test must work
identically after the split.

---

## Target Structure

```
web/
  index.html              ← markup only (was compare.html)
  css/
    styles.css            ← all CSS extracted from <style>
  js/
    main.js               ← entry point, wires modules, exposes test hooks
    constants.js          ← COLUMNS, SVG_W, PAD, PANEL_DEFS, HEATMAP_*
    appState.js           ← store, render-state, cursor/drag state, persistence
    dataTransforms.js     ← parquet/CSV/sidecar loading, segments, annotation
    calculations.js       ← resample, Δt, smoothing, sectors, track geometry
    renderer.js           ← SVG panel rendering, circuit map, heatmap, legend
    eventHandlers.js      ← cursor, zoom, file-load UI, pickers, colour setup
    validators.js         ← hex colour, zoom-range, picker-value parsing
    utils.js              ← formatDuration, badges, shortVehicle, error display
```

No build step. No bundler. Pure ESM `<script type="module">` with the same
two CDN imports (hyparquet, hyparquet-compressors). Runs from any static
server or `python -m http.server` in `web/`.

---

## Module Responsibilities

### `index.html`
- `<!DOCTYPE html>` + `<head>` with `<link rel="stylesheet" href="css/styles.css">`
- Full DOM structure (loader panel, pickers, legend, plot area, circuit map,
  zoom-selection rect) — unchanged markup
- Single `<script type="module" src="js/main.js"></script>` at the bottom

### `css/styles.css`
- Verbatim extract of the current `<style>` block (lines 7-310)
- No changes to selectors, custom properties, or values

### `js/constants.js`
Exports only pure data — no DOM access, no imports beyond standard JS.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `COLUMNS` | 403-410 | Column names read from parquet |
| `SVG_W`, `PAD`, `PLOT_W` | 412-416 | SVG viewBox layout |
| `MAP_SIZE`, `MAP_PAD` | 417-419 | Circuit map dimensions |
| `PANEL_DEFS` | 421-479 | 8 panel definitions (id, label, height, channels, yFixed, etc.) |
| `HEATMAP_RAMPS` | 1179-1188 | Colour ramp functions for speed/brake/throttle |
| `HEATMAP_CHANNELS` | 1189 | Map mode → column name |

### `js/appState.js`
Owns all mutable application state. Other modules import getters/setters —
never mutate state by reaching into the object directly.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `store` | 481 | `Map` of storeKey → session entry |
| `storeKey(file)` | 482 | `${file.name}::${file.size}` |
| `pendingSidecars` | 1596 | `Map` of stem → sidecar JSON |
| `fileStem(name)` | 1597 | Strip extension |
| `currentSessionBins` | 1116 | Resampled session channels (set/get) |
| `currentRefBins` | 1117 | Resampled ref channels |
| `currentMaxDist` | 1118 | Max distance for current render |
| `currentDtBins` | 1119 | Smoothed Δt array |
| `currentTrackX/Z` | 1120-1121 | Resampled track coords |
| `currentZoomRange` | 1122 | `{start, end}` |
| `currentOverlapRange` | 1123 | Overlap window |
| `trackTransform` | 1124 | Map transform functions |
| `state` | 1847 | `{maxDist, dragging, dragStartX, dragStartDist}` |
| `lastRenderParams` | ~1490 | Stored args for re-render on zoom |
| `LAP_COLOUR_DEFAULTS` | 1126 | `{session, ref}` hex defaults |
| `LAP_COLOUR_LS_KEY` | 1127 | localStorage key for colours |
| `ZOOM_LS_KEY` | 1155 | localStorage key for zoom |

### `js/dataTransforms.js`
All data ingestion: parquet reading, CSV parsing, sidecar attachment,
segment building and annotation. Imports `constants.js` and `appState.js`.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `fileToAsyncBuffer(file)` | 489-496 | Wrap `File` as hyparquet asyncBuffer |
| `readColumns(file)` | 498-529 | Stream parquet columns via hyparquet |
| `buildSegments(lapNumbers)` | 533-546 | Split into laps by lap_number change |
| `annotateSegments(segs, dists, times)` | 568-619 | Classify partial/rolling/fastest |
| `loadFile(file)` | 1730-1787 | Dispatch .json/.csv/.parquet loading |
| `loadDeltabestCsv(file)` | 1607-1706 | Parse TinyPedal deltabest CSV |
| `loadSidecar(file)` | 1708-1728 | Parse JSON sidecar, attach to store |

CDN imports (`parquetRead`, `parquetMetadataAsync`, `compressors`) move
here — they are only used by the data layer.

### `js/calculations.js`
Pure functions — no DOM, no state mutation. Take arrays in, return arrays out.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `interpAt(xs, ys, x)` | 623-634 | Binary search + linear interpolation |
| `resample(dists, vals, maxDist)` | 636-647 | Interpolate onto 1 m distance bins |
| `computeDeltaT(sTime, rTime)` | 656-661 | Subtract lap_time_s → ms |
| `computeKeepIndices(dists, times, maxD)` | 670-680 | Filter boundary artifacts |
| `smoothLapTime(times, dists, keep)` | 690-704 | Linear interp across plateaus |
| `smoothDt(dt)` | 719-731 | 41-bin symmetric boxcar |
| `smoothGear(gear)` | 738-754 | Fill ≤5-frame neutral runs |
| `deriveSectorDistances(data, seg, next)` | 758-803 | S1/S2/S3 distance markers |
| `niceRange(vals, fixed)` | 807-814 | Auto y-range with 5% margin |
| `computeTrackBounds(xs, zs)` | 830-840 | Min/max of track coords |
| `buildTrackTransform(bounds, size, pad)` | 842-854 | Scale/offset for circuit map |
| `computeMedianFrameDistanceDelta(dists)` | ~860 | Detect coarse distance resolution |

### `js/renderer.js`
All SVG string construction and DOM updates for panels and the circuit map.
Imports `constants.js`, `appState.js`, `calculations.js`.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `buildPolylinePts(xs, ys, ...)` | 816-826 | SVG polyline points (with step) |
| `buildTrackPolylinePts(xs, zs, tx)` | 828 | Track outline points |
| `renderPanel(def, bins, maxD, sectors, zoom)` | 880-1010 | 7-panel SVG renderer |
| `renderDtPanel(dtBins, maxD, sectors, zoom, overlap)` | 1014-1112 | Δt panel with overlap clipping |
| `renderCircuitMap(mode)` | 1192-1217 | Circuit map (outline or heatmap) |
| `renderHeatmapSegments(bins, col, ramp, tx)` | 1219-1249 | Coloured 2 m segments |
| `renderMapLegend(mode, bins)` | 1251-1271 | Gradient bar + min/max labels |
| `updateZoomArc(zoom, maxD)` | 1273-1302 | Yellow zoom arc on map |
| `updateCursorDot(dist)` | 1921-1938 | Cyan dot on map at cursor |
| `renderAll(sEntry, sSeg, rEntry, rSeg)` | 1304-1492 | Master orchestrator |

`renderAll` is the largest function (~190 lines). It stays in `renderer.js`
because it is fundamentally a render pipeline — it calls calculations,
writes bins into state, then builds HTML. Splitting it further would add
indirection without a clear boundary.

### `js/eventHandlers.js`
All `addEventListener` wiring and DOM-event callbacks. Imports
`appState.js`, `renderer.js`, `dataTransforms.js`, `validators.js`, `utils.js`.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `initEventHandlers()` | — | Wire all listeners (called once from main.js) |
| `updateCursorPosition(e)` | 1853-1919 | Cursor tracking + tooltip |
| `initZoomHandlers()` | 1940-2055 | Drag-to-zoom, dblclick, Escape |
| `initFileLoadHandlers()` | 2069-2078 | Load button + file input |
| `initCompareHandlers()` | 2080-2109 | Compare button + picker changes |
| `initMapModeHandler()` | 2112-2115 | Map mode selector |
| `initColourPickers()` | 2117-2148 | Colour inputs + reset button |

The top-level `initEventHandlers()` calls each `init*` sub-function.

### `js/validators.js`
Small pure-function module — no DOM, no state.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `isValidHexColour(s)` | ~1140 | `/^#[0-9a-fA-F]{6}$/` |
| `validateZoomRange(z, maxDist)` | 1163-1177 | Bounds-check + min-span 10 m |
| `parsePickerValue(val)` | 1587-1594 | `"key::segIdx"` → `{key, segIdx}` |

### `js/utils.js`
Formatting helpers and simple DOM utilities.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `formatDuration(s)` | 1496-1500 | Seconds → `"M:SS.sss"` |
| `lapStatusBadges(seg)` | 1502-1507 | `" (rolling, partial)"` or `""` |
| `formatPickLabel(entry, seg, idx)` | 1509-1521 | Full picker option label |
| `shortVehicle(name)` | 1789-1798 | Abbreviate vehicle string |
| `shortSetup(name)` | 1800-1803 | Strip `.svm` extension |
| `showError(msg)` | 2057-2060 | Display error in `#error-msg` |
| `clearError()` | 2062-2065 | Hide error |
| `applyLapColour(slot, hex)` | 1130-1132 | Set CSS custom property |
| `persistLapColours(colours)` | 1134-1136 | Write to localStorage |
| `loadPersistedColours()` | 1138-1152 | Read + validate from localStorage |
| `persistZoom(zoom)` | 1157-1159 | Write to localStorage |
| `loadPersistedZoom(maxDist)` | 1161-1177 | Read + validate from localStorage |

### `js/main.js`
Thin entry point — no logic of its own.

```js
import { initEventHandlers } from './eventHandlers.js';
import { loadPersistedColours, applyLapColour } from './utils.js';
import { LAP_COLOUR_DEFAULTS } from './appState.js';
// … remaining imports for debug hooks

/* ── Boot ──────────────────────────────────────────── */
const colours = loadPersistedColours() ?? LAP_COLOUR_DEFAULTS;
applyLapColour('session', colours.session);
applyLapColour('ref', colours.ref);

initEventHandlers();

/* ── Test hooks (Playwright) ──────────────────────── */
window.__getSessionKeys   = () => { … };
window.__resamplerDebug   = (key, seg) => { … };
window.__dtDebug          = (sKey, sSeg, rKey, rSeg) => { … };
window.__dtDebugOverlap   = (sKey, sSeg, rKey, rSeg) => { … };
```

The four `window.__*` debug functions stay here, importing whatever they
need from `appState` and `calculations`.

---

## Module Dependency Graph

```
main.js
  ├── appState.js        (state)
  ├── constants.js       (pure data)
  ├── utils.js           (formatting, persistence)
  ├── eventHandlers.js
  │     ├── appState.js
  │     ├── renderer.js
  │     │     ├── constants.js
  │     │     ├── appState.js
  │     │     └── calculations.js  (pure functions)
  │     ├── dataTransforms.js
  │     │     ├── constants.js
  │     │     ├── appState.js
  │     │     └── calculations.js
  │     ├── validators.js          (pure functions)
  │     └── utils.js
  └── calculations.js   (for debug hooks)
```

No circular dependencies. `constants.js`, `calculations.js`, and
`validators.js` are leaf modules with zero internal imports.

---

## Picker / Session-List UI

`rebuildPickers()` (lines 1523-1579) and `addSessionEntry()` /
`refreshSessionListBadges()` (lines 1805-1843) are DOM-manipulation
functions tied to the data layer (they read from `store`). They go in
**`dataTransforms.js`** alongside loading — they are the "data → DOM
projection" that runs after every load. Alternatively they could live in a
small `pickers.js`, but the coupling to `store` and `annotateSegments`
makes `dataTransforms.js` the natural home. If the module grows past ~400
lines, split at that point.

`updateCompareBtn()` (1581-1585) and `setBadge()` (1840-1843) are trivial
DOM helpers — they go in `utils.js`.

---

## Implementation Steps

### Step 0 — Preparation

- Create `web/css/` and `web/js/` directories.
- Verify all Playwright tests pass on the current monolithic file
  (`node scripts/test_m5.js`, `test_m6.js`, `test_m6_extras.js`,
  `test_f1f2.js`). Record pass count as the baseline.

### Step 1 — Extract CSS

- Copy the `<style>` block (lines 7-310) verbatim into `web/css/styles.css`.
- Replace the `<style>` block in `compare.html` with
  `<link rel="stylesheet" href="css/styles.css">`.
- Verify render is identical (visual spot-check).

### Step 2 — Extract leaf modules (no DOM)

Create the three leaf modules that have zero DOM access and zero internal
imports:

1. **`js/constants.js`** — cut `COLUMNS`, `SVG_W`, `PAD`, `PLOT_W`,
   `MAP_SIZE`, `MAP_PAD`, `PANEL_DEFS`, `HEATMAP_RAMPS`, `HEATMAP_CHANNELS`.
   Add `export` to each.

2. **`js/calculations.js`** — cut every pure-math function listed above.
   Import nothing. Add `export` to each.

3. **`js/validators.js`** — cut the three validation functions. Add `export`.

At this point the remaining `<script>` in `compare.html` imports these
three modules and everything else stays inline. Run tests after each
extraction to catch broken references immediately.

### Step 3 — Extract `appState.js`

Move all global state declarations (`store`, `storeKey`, `pendingSidecars`,
`fileStem`, `currentSessionBins`, …, `state`, localStorage keys, colour
defaults) into `js/appState.js`. Export getters/setters or a plain object
— prefer the simplest approach (exported `let` bindings with setter
functions where mutation is needed from outside).

### Step 4 — Extract `utils.js`

Move formatting helpers, persistence helpers (`applyLapColour`,
`persistLapColours`, `loadPersistedColours`, `persistZoom`,
`loadPersistedZoom`), error display, badge helpers.

### Step 5 — Extract `dataTransforms.js`

Move parquet/CSV/sidecar loading, segment building and annotation,
picker/session-list DOM updates (`rebuildPickers`, `addSessionEntry`,
`refreshSessionListBadges`). This module imports `constants`, `appState`,
`calculations`, `utils`, and the two CDN hyparquet packages.

### Step 6 — Extract `renderer.js`

Move all SVG rendering functions (`renderPanel`, `renderDtPanel`,
`renderAll`, circuit map functions, polyline builders). Imports `constants`,
`appState`, `calculations`.

### Step 7 — Extract `eventHandlers.js`

Move all event-listener setup and callbacks. Exports `initEventHandlers()`.
Imports everything it needs from the other modules.

### Step 8 — Create `main.js` and `index.html`

- Write `js/main.js` as the thin boot + debug-hook entry point.
- Create `web/index.html` — identical DOM to old `compare.html`, but with
  `<link>` for CSS and `<script type="module" src="js/main.js">` only.
- Delete the old `compare.html`.

### Step 9 — Update test infrastructure

All Playwright test files hard-code `HTML_FILE` and use a minimal HTTP
server that serves only one file. Update each test's server to serve the
entire `web/` directory with correct MIME types:

```js
const MIME = {
  '.html': 'text/html',
  '.css':  'text/css',
  '.js':   'application/javascript',
  '.json': 'application/json',
};

function startServer() {
  const server = http.createServer((req, res) => {
    const safePath = path.normalize(req.url).replace(/^(\.\.[\/\\])+/, '');
    const filePath = path.join(WEB_DIR, safePath === '/' ? 'index.html' : safePath);
    const ext = path.extname(filePath);
    res.setHeader('Content-Type', MIME[ext] || 'application/octet-stream');
    res.end(fs.readFileSync(filePath));
  });
  ...
}
```

Update the `HTML_FILE` constant to `WEB_DIR` pointing at `web/`.
Update all test files: `test_m4.js`, `test_m5.js`, `test_m6.js`,
`test_m6_extras.js`, `test_f1f2.js`, `verify_deltat_js.js`,
`verify_render_perf.js`.

### Step 10 — Full regression

- Run every Playwright test. Pass count must match or exceed baseline.
- Manual spot-check: load a session + sidecar + CSV, pick laps, compare,
  zoom, hover tooltip, change colours, reset colours, switch map mode.
- Verify `file://` still works — it won't for ESM cross-origin, so
  document the one-liner `python3 -m http.server -d web 8000` in the
  README and CLAUDE.md.

---

## Constraints

| Constraint | Rationale |
|-----------|-----------|
| No bundler / build step | Project philosophy: open `index.html`, done |
| ESM only (`type="module"`) | Already used for CDN imports; native browser support |
| Same two CDN imports | hyparquet + hyparquet-compressors, unchanged |
| No new dependencies | Keep zero-install for the browser side |
| Playwright tests unbroken | Automated gate — every existing assertion passes |
| `window.__*` debug hooks preserved | Tests call these directly |
| No behaviour change | Pixel-identical rendering, identical interactions |

---

## Risks & Mitigations

**MIME types on `file://`.**  ESM `import` from `file://` is blocked by
browser same-origin policy in most browsers. Mitigation: document the local
server one-liner; CI already uses an HTTP server.

**Circular imports.** The dependency graph above is acyclic by design.
`renderer.js` and `eventHandlers.js` both need `appState.js`, but neither
imports the other. `renderAll` is in `renderer.js`; event handlers call it
via a direct import, not a callback.

**Large `renderAll` function.** At ~190 lines it is the biggest single
function. It stays in `renderer.js` as a deliberate choice — it is a
render pipeline and splitting it would scatter the data-flow across files
with no clear boundary. If future work adds panels, extracting a
`renderPipeline.js` would be the next natural split.

**Test server change.** The server update is mechanical but touches 7 files.
A shared `scripts/lib/test-server.js` helper could DRY this up, but that
is optional and can be done in a follow-up.
