# Web Viewer Refactoring Plan

Refactor the monolithic `web/compare.html` (2,208 lines) into a clean
multi-file ESM architecture. Zero behaviour change — every panel, tooltip,
zoom interaction, colour picker, CSV ingest, and Playwright test must work
identically after the split.

**Incremental delivery:** Every step commits directly to `main`. At every step, two artifacts work:
1. `web/compare.html` — served via HTTP (development)
2. `dist/compare.html` — standalone single file, `file://` (users)

The build pipeline and test infrastructure are established first
(walking skeleton), so both artifacts exist from Step 1 onward.

---

## Target Structure

```
web/
  compare.html            ← markup only (same filename, no rename)
  css/
    styles.css            ← all CSS extracted from <style>
  js/
    main.js               ← entry point, wires modules, exposes test hooks
    constants.js          ← COLUMNS, SVG_W, PAD, PANEL_DEFS, HEATMAP_*, LS keys
    appState.js           ← store, render-state, cursor/drag state
    dataTransforms.js     ← parquet/CSV/sidecar parsing (pure data, no DOM)
    pickers.js            ← picker/session-list DOM projection from store
    calculations.js       ← resample, Δt, smoothing, sectors, track geometry
    renderer.js           ← SVG panel rendering, circuit map, heatmap, legend
    eventHandlers.js      ← cursor, zoom, file-load orchestration, colour setup
    validators.js         ← hex colour validation, picker-value parsing
    utils.js              ← formatDuration, badges, shortVehicle, error display
dist/
  compare.html            ← standalone single-file build (file:// compatible)
scripts/
  bundle.js               ← inlines CSS + bundled JS into dist/compare.html
  lib/
    test-server.js         ← shared HTTP server helper for Playwright tests
```

Pure ESM `<script type="module">` with the same two CDN imports
(hyparquet, hyparquet-compressors). The modular `web/` layout is the
source of truth — it runs from any static server or
`python -m http.server` in `web/`. A one-step build (`npm run build`)
produces `dist/compare.html`, a self-contained single file that works
via `file://` for end-user use. When this project moves to Electron,
the Electron shell loads `web/` directly and the build step becomes
unnecessary.

---

## Module Responsibilities

### `compare.html`
- `<!DOCTYPE html>` + `<head>` with `<link rel="stylesheet" href="css/styles.css">`
- Full DOM structure (loader panel, pickers, legend, plot area, circuit map,
  zoom-selection rect) — unchanged markup
- Single `<script type="module" src="js/main.js"></script>` at the bottom
- A small inline `<script>` (not `type="module"`) that sets a timeout and
  checks whether `main.js` initialised. If not, shows a visible error:
  *"Module loading failed. Serve this directory from an HTTP server:
  `python3 -m http.server -d web`"*. This catches silent failures when
  someone opens the modular `web/compare.html` via `file://` instead of
  the standalone `dist/compare.html`.

### `css/styles.css`
- Verbatim extract of the current `<style>` block (lines 7-310)
- No changes to selectors, custom properties, or values

### `js/constants.js`
Exports pure data and stateless colour-ramp functions — no DOM access,
no imports beyond standard JS.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `COLUMNS` | 403-410 | Column names read from parquet |
| `SVG_W`, `PAD`, `PLOT_W` | 412-416 | SVG viewBox layout |
| `MAP_SIZE`, `MAP_PAD` | 417-419 | Circuit map dimensions |
| `PANEL_DEFS` | 421-479 | 8 panel definitions (id, label, height, channels, yFixed, etc.) |
| `HEATMAP_RAMPS` | 1180-1187 | Colour ramp functions for speed/brake/throttle |
| `HEATMAP_CHANNELS` | 1188 | Map mode → column name |
| `LAP_COLOUR_DEFAULTS` | 1127 | `{session, ref}` hex defaults |
| `LAP_COLOUR_LS_KEY` | 1128 | localStorage key for colours |
| `ZOOM_LS_KEY` | 1156 | localStorage key for zoom |

### `js/appState.js`
Owns all mutable application state. Other modules import getters/setters —
never mutate state by reaching into the object directly.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `store` | 483 | `Map` of storeKey → session entry |
| `pendingSidecars` | 1600 | `Map` of stem → sidecar JSON |
| `currentSessionBins` | 1116 | Resampled session channels (set/get) |
| `currentRefBins` | 1117 | Resampled ref channels |
| `currentMaxDist` | 1118 | Max distance for current render |
| `currentDtBins` | 1119 | Smoothed Δt array |
| `currentTrackX/Z` | 1120-1121 | Resampled track coords |
| `currentZoomRange` | 1122 | `{start, end}` |
| `currentOverlapRange` | 1123 | Overlap window |
| `trackTransform` | 1124 | Map transform functions |
| `currentMapMode` | 1190 | Current map display mode (`'outline'` or heatmap channel) |
| `state` | 1847 | `{maxDist, dragging, dragStartX, dragStartDist, currentRenderParams}` |

Note: `state.currentRenderParams` (set at lines 2090/2104, read at
lines 2026/2036/2053) stores the `[sEntry, segIdx, rEntry, segIdx]`
tuple so zoom/reset handlers can re-invoke `renderAll` without the
pickers. It is set in `eventHandlers.js` and read in `eventHandlers.js`,
so it stays on the shared `state` object exported from `appState.js`.

### `js/dataTransforms.js`
Pure data ingestion: parquet reading, CSV parsing, sidecar attachment,
segment building and annotation. **No DOM access** — pure data in, data
out. Imports `constants.js`, `appState.js`, `calculations.js`, and
`utils.js` (for `storeKey`, `fileStem`).

The three high-level loading functions (`loadFile`, `loadDeltabestCsv`,
`loadSidecar`) in the current monolith mix data parsing with DOM updates
(calling `addSessionEntry`, `setBadge`, `rebuildPickers`, `showError`,
`document.getElementById`). To preserve the "no DOM" contract, each is
split into a pure-data core here and a thin DOM-orchestration wrapper in
`eventHandlers.js`:

| Export | Current lines | Description |
|--------|--------------|-------------|
| `fileToAsyncBuffer(file)` | 489-496 | Wrap `File` as hyparquet asyncBuffer |
| `readColumns(file)` | 498-529 | Stream parquet columns via hyparquet |
| `buildSegments(lapNumbers)` | 533-546 | Split into laps by lap_number change |
| `annotateSegments(segs, dists, times)` | 568-619 | Classify partial/rolling/fastest |
| `parseParquetFile(file)` | from 1730-1787 | Parse parquet → returns `{key, entry, missing}` or throws; does NOT touch DOM or store |
| `parseDeltabestCsv(file)` | from 1607-1706 | Parse CSV → returns `{key, entry}` or throws; does NOT touch DOM or store |
| `parseSidecar(file)` | from 1708-1728 | Parse JSON → returns `{stem, sidecar}` or throws |

The `PARTIAL_DIST_FRAC`, `PARTIAL_DUR_FRAC`, and `ROLLING_DIST_M`
constants (lines 565-567) stay as module-level constants inside
`dataTransforms.js` — they are only used by `annotateSegments`.

CDN imports (`parquetRead`, `parquetMetadataAsync`, `compressors`) move
here — they are only used by the data layer. These imports migrate in
Step 5 when this module is extracted; during earlier hybrid steps (2–4)
they remain in the inline `<script>` block.

**How the split works at extraction time (Step 5):**

The current `loadFile` (lines 1730-1787) becomes two pieces:

1. `parseParquetFile(file)` in `dataTransforms.js` — everything up to
   and including `store.set(...)` is replaced by returning the entry
   object. The function does: `readColumns` → `buildSegments` →
   `annotateSegments` → sidecar lookup from `pendingSidecars` →
   returns `{ key, fileName, data, segments, hasSlip, hasSectors,
   sidecar, missingCols }`.

2. `handleFileLoad(file)` in `eventHandlers.js` — calls
   `parseParquetFile`, catches errors, calls `addSessionEntry` /
   `setBadge` / `rebuildPickers` / `showError` / updates
   `#load-status`. Same pattern for CSV and sidecar.

The same split applies to `loadDeltabestCsv` → `parseDeltabestCsv` +
`handleCsvLoad`, and `loadSidecar` → `parseSidecar` +
`handleSidecarLoad`. The top-level dispatcher `loadFile` (route by
extension) moves to `eventHandlers.js` as `handleFileLoad`.

### `js/pickers.js`
Picker / session-list DOM projection. Reads from `store` and rebuilds
`<select>` options and session-list badges after every file load. Imports
`appState.js`, `utils.js`, `constants.js`.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `rebuildPickers()` | 1523-1579 | Rebuild session/ref `<select>` from `store` |
| `refreshSessionListBadges()` | 1805-1813 | Re-stamp fastest/rolling badges |
| `addSessionEntry(name, key, statusText)` | 1817-1838 | Append session to `#session-list`, wire remove button |
| `updateCompareBtn()` | 1581-1585 | Enable/disable compare button |

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

**Signature note:** Several map/circuit functions in the monolith take
zero arguments and read module-scope state (`currentTrackX`,
`currentMapMode`, `currentZoomRange`, etc.). In the modular version
they import that state from `appState.js` instead — the signatures stay
parameter-free (no rewrite needed) because they call getters on the
imported state module. This is deliberate: these functions are called
from multiple sites and parameterising them would add boilerplate
without benefit. The only change at extraction time is replacing bare
`currentTrackX` with `appState.currentTrackX` (or a destructured
import).

| Export | Current lines | Description |
|--------|--------------|-------------|
| `buildPolylinePts(xs, ys, ...)` | 816-826 | SVG polyline points (with step) |
| `buildTrackPolylinePts(xs, zs, toMapX, toMapZ)` | 856-864 | Track outline points |
| `renderPanel(def, bins, maxD, sectors, zoom)` | 880-1010 | 7-panel SVG renderer |
| `renderDtPanel(def, dtBins, maxD, sectors, zoom, overlap)` | 1014-1112 | Δt panel with overlap clipping |
| `renderCircuitMap()` | 1192-1217 | Circuit map — reads `currentMapMode` from appState (no args) |
| `renderHeatmapSegments(mode)` | 1219-1249 | Coloured segments — single `mode` arg, reads bins/transform from appState |
| `renderMapLegend()` | 1251-1271 | Gradient bar — reads mode/bins from appState (no args) |
| `updateZoomArc()` | 1273-1302 | Yellow zoom arc — reads zoom/track from appState (no args) |
| `updateCursorDot(binIdx)` | 1921-1938 | Cyan dot on map at cursor distance bin |
| `renderAll(sEntry, sSeg, rEntry, rSeg)` | 1304-1492 | Master orchestrator |

`renderAll` is the largest function (~190 lines). It stays in `renderer.js`
because it is fundamentally a render pipeline — it calls calculations,
writes bins into state, then builds HTML. Splitting it further would add
indirection without a clear boundary. Note that `renderAll` both computes
state (writing to appState) and renders DOM — this is intentional; it is
the data→render pipeline, not a pure view function.

### `js/eventHandlers.js`
All `addEventListener` wiring and DOM-event callbacks. Also owns the
file-load orchestration wrappers (`handleFileLoad`, `handleCsvLoad`,
`handleSidecarLoad`) that call the pure parsers in `dataTransforms.js`
and then update the DOM via `pickers.js` / `utils.js`.

Imports `appState.js`, `renderer.js`, `dataTransforms.js`, `pickers.js`,
`validators.js`, `utils.js`.

**Module-scope DOM lookups:** The monolith declares `plotArea`,
`cursorLine`, `tooltip` as top-level `const` via `getElementById`
(lines 1849-1851). In the modular version these move inside
`initEventHandlers()` (or into a module-level lazy-init pattern) so
they execute only after the DOM is ready. With `<script type="module">`
at the bottom of `<body>` the DOM is already parsed, so the timing is
safe — but the lookups must not be at the top of the module file
because ESM modules execute in order and a future import reordering
could break them. Keep them inside `initEventHandlers()` as local
`const` bindings, or as module-level `let` bindings assigned inside
`initEventHandlers()`.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `initEventHandlers()` | — | Wire all listeners (called once from main.js) |
| `updateCursorPosition(e)` | 1853-1919 | Cursor tracking + tooltip |
| `initZoomHandlers()` | 1940-2055 | Drag-to-zoom, dblclick, Escape |
| `handleFileLoad(file)` | from 1730-1787 | Dispatch .json/.csv/.parquet, call parser, update DOM/store |
| `handleCsvLoad(file)` | from 1607-1706 | Call `parseDeltabestCsv`, update DOM/store |
| `handleSidecarLoad(file)` | from 1708-1728 | Call `parseSidecar`, attach to store, update DOM |
| `initFileLoadHandlers()` | 2069-2078 | Load button + file input (calls `handleFileLoad`) |
| `initCompareHandlers()` | 2080-2109 | Compare button + picker changes |
| `initMapModeHandler()` | 2112-2115 | Map mode selector |
| `initColourPickers()` | 2117-2148 | Colour inputs + reset button |
| `syncColourInputs(colours)` | 2122-2125 | Set colour input `.value` from object (internal helper, not exported) |
| `setLapColours(colours, persist)` | 2127-2131 | Apply + persist colour pair (internal helper, not exported) |

The top-level `initEventHandlers()` calls each `init*` sub-function.

`syncColourInputs` and `setLapColours` (lines 2122-2131) are internal
helpers used only within `initColourPickers`. They stay in
`eventHandlers.js` as unexported module-private functions.

**Boot-time colour init overlap:** The monolith initialises colours at
lines 2133-2135 (outside any function, at module load). In the modular
version, `main.js` handles the boot-time colour setup (calling
`loadPersistedColours` + `applyLapColour`), and `initColourPickers()`
handles wiring the `<input>` listeners + syncing the input values.
The colour-init code at 2133-2135 is therefore split: the CSS property
application stays in `main.js`; the input `.value` sync moves into
`initColourPickers()`. No duplication.

### `js/validators.js`
Small pure-function module — no DOM, no state.

| Export | Current lines | Description |
|--------|--------------|-------------|
| `isValidHexColour(s)` | ~1129 | Wraps `HEX_RE.test(s)` — the monolith has only the raw regex `const HEX_RE = /^#[0-9a-fA-F]{6}$/;` at line 1129; create a one-line wrapper `export function isValidHexColour(s) { return /^#[0-9a-fA-F]{6}$/.test(s); }` so callers get a semantic function rather than a bare regex |
| `parsePickerValue(val)` | 1587-1594 | `"key::segIdx"` → `{key, segIdx}` |

Note: the monolith has no standalone `validateZoomRange` function.
The zoom validation logic is embedded inside `loadPersistedZoom`
(lines 1168-1177), which lives in `utils.js`. No separate validator
export is needed.

### `js/utils.js`
Formatting helpers, simple DOM utilities, and persistence helpers.
Imports `validators.js` (for `isValidHexColour` used by
`loadPersistedColours`) and `constants.js` (for localStorage keys).

| Export | Current lines | Description |
|--------|--------------|-------------|
| `storeKey(file)` | 485 | `${file.name}::${file.size}` |
| `fileStem(name)` | 1602 | Strip extension |
| `formatDuration(s)` | 1496-1500 | Seconds → `"M:SS.sss"` |
| `lapStatusBadges(seg)` | 1502-1507 | `" (rolling, partial)"` or `""` |
| `formatPickLabel(entry, segIdx)` | 1509-1521 | Full picker option label |
| `shortVehicle(name)` | 1789-1798 | Abbreviate vehicle string |
| `shortSetup(name)` | 1800-1803 | Strip `.svm` extension |
| `showError(msg)` | 2057-2060 | Display error in `#error-msg` |
| `clearError()` | 2062-2065 | Hide error |
| `setBadge(el, cls, text)` | 1840-1843 | Set badge class + text |
| `applyLapColour(slot, hex)` | 1130-1132 | Set CSS custom property |
| `persistLapColours(colours)` | 1135-1143 | Write to localStorage |
| `loadPersistedColours()` | 1145-1153 | Read + validate from localStorage |
| `persistZoom(zoom, maxDist)` | 1158-1166 | Write to localStorage (add `maxDist` parameter — the monolith reads `currentMaxDist` from module scope; in the modular version callers pass it explicitly so `utils.js` does not depend on `appState.js`) |
| `loadPersistedZoom(maxDist)` | 1168-1177 | Read + validate from localStorage |

### `js/main.js`
Thin entry point — no logic of its own.

```js
import { initEventHandlers } from './eventHandlers.js';
import { loadPersistedColours, applyLapColour } from './utils.js';
import { LAP_COLOUR_DEFAULTS } from './constants.js';
// … remaining imports for debug hooks

/* ── Boot ──────────────────────────────────────────── */
const colours = loadPersistedColours() ?? LAP_COLOUR_DEFAULTS;
applyLapColour('session', colours.session);
applyLapColour('ref', colours.ref);

initEventHandlers();

/* ── Test hooks (Playwright) ──────────────────────── */
window.__getSessionKeys   = () => { … };
window.__resamplerDebug   = (key, seg) => { … };
window.__refResamplerDebug = (key, seg) => { … };  // alias for __resamplerDebug
window.__dtDebug          = (sKey, sSeg, rKey, rSeg) => { … };
window.__dtDebugOverlap   = (sKey, sSeg, rKey, rSeg) => { … };
```

The five `window.__*` debug functions stay here, importing whatever they
need from `appState`, `calculations`, and `dataTransforms`.

---

## Module Dependency Graph

```
main.js
  ├── appState.js        (state)
  ├── constants.js       (pure data)
  ├── utils.js           (formatting, persistence)
  │     ├── validators.js          (pure functions)
  │     └── constants.js
  ├── eventHandlers.js
  │     ├── appState.js
  │     ├── renderer.js
  │     │     ├── constants.js
  │     │     ├── appState.js
  │     │     └── calculations.js  (pure functions)
  │     ├── dataTransforms.js      (pure data parsing, NO DOM)
  │     │     ├── constants.js
  │     │     ├── appState.js      (only for pendingSidecars lookup)
  │     │     ├── utils.js         (for storeKey, fileStem)
  │     │     └── calculations.js
  │     ├── pickers.js
  │     │     ├── appState.js
  │     │     ├── utils.js
  │     │     └── constants.js
  │     ├── validators.js
  │     └── utils.js
  ├── calculations.js   (for debug hooks)
  └── dataTransforms.js  (for debug hooks: resample, smoothLapTime, etc.)
```

No circular dependencies. `constants.js`, `calculations.js`, and
`validators.js` are leaf modules with zero internal imports.
`dataTransforms.js` is DOM-free — all DOM orchestration for file
loading lives in `eventHandlers.js` (the `handleFileLoad` /
`handleCsvLoad` / `handleSidecarLoad` wrappers).

---

## Picker / Session-List UI

`rebuildPickers()` (lines 1523-1579), `refreshSessionListBadges()`
(lines 1805-1813), `addSessionEntry()` (lines 1817-1838), and
`updateCompareBtn()` (1581-1585) are DOM-manipulation functions that
project `store` contents into the picker `<select>` elements and session
list. They go in **`pickers.js`** — not `dataTransforms.js`, which stays
DOM-free so it remains testable without a browser environment. The
coupling to `store` is handled via a normal import of `appState.js`,
same as every other module.

`setBadge()` (1840-1843) is a trivial DOM helper — it goes in `utils.js`.

---

## Implementation Steps

Each step produces a commit directly on `main`. The readiness gate for every step is:

1. All Playwright tests pass against `web/` (via HTTP server)
2. `npm run build` succeeds
3. `dist/compare.html` works via `file://` (manual spot-check or
   automated test — at minimum, load, compare, zoom, tooltip)

If any step breaks the gate, revert and fix before proceeding.

---

### Step 1 — Walking skeleton: build pipeline + test infrastructure

Establish the two delivery channels (`web/` via HTTP, `dist/` via
`file://`) and the test infrastructure before touching any application
code. After this step, every subsequent extraction automatically
produces a working `dist/compare.html`.

**1a. Install esbuild, create directories.**

```
npm install --save-dev esbuild
```

Create `web/css/`, `web/js/`, and `dist/` directories (e.g.,
`mkdir web\css web\js dist` on Windows, or through your editor).

**1b. Write `scripts/bundle.js`.**

The bundle script handles both the hybrid state (inline `<script>` with
`import` statements) and the final state (`<script src="js/main.js">`).
It works at every step of the refactor:

```
1. Read web/compare.html
2. If <link rel="stylesheet" href="css/styles.css"> found:
   - Read web/css/styles.css
   - Replace the <link> with <style> + CSS contents + </style>
3. If <script type="module" src="js/main.js"> found:
   - Run esbuild on web/js/main.js --bundle --format=esm
     with external: ['https://*']
   - Replace the <script src> with <script type="module"> + bundled JS
4. Else if inline <script type="module"> contains relative imports
   (from './js/...'):
   - Extract inline script to a temp file
   - Run esbuild on temp file --bundle --format=esm
     with external: ['https://*']
   - Replace inline script with bundled result
5. Else: no JS bundling needed (monolith, no relative imports yet)
6. Remove the module-load fallback <script> if present
7. Write dist/compare.html
```

At Step 1, with no modules extracted yet, this is effectively a copy.
At Step 2+ (CSS extracted), it inlines CSS. At Step 3+ (JS modules
exist), it bundles relative imports via esbuild. At the final step
(main.js exists), it bundles the entry point. The script never needs
rewriting — it handles every intermediate state.

**1c. Write `scripts/lib/test-server.js`** — shared directory-serving
HTTP server helper.

```js
const MIME = {
  '.html': 'text/html',
  '.css':  'text/css',
  '.js':   'application/javascript',
  '.json': 'application/json',
};

function startServer(webDir) {
  const server = http.createServer((req, res) => {
    const safePath = path.normalize(req.url).replace(/^(\.\.[\/\\])+/, '');
    const filePath = path.join(webDir, safePath === '/' ? 'compare.html' : safePath);
    const ext = path.extname(filePath);
    res.setHeader('Content-Type', MIME[ext] || 'application/octet-stream');
    res.end(fs.readFileSync(filePath));
  });
  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => {
      resolve({ server, port: server.address().port });
    });
  });
}
```

**1d. Convert all 7 test files to use the shared helper.**

- **HTTP tests** (`test_m4.js`, `test_m5.js`, `test_m6.js`,
  `test_f1f2.js`): replace their single-file server
  (`res.end(fs.readFileSync(HTML_FILE))`) with the directory-serving
  helper. The monolith works identically behind either server, so this
  is a no-op for behaviour — but it means these tests won't 404 on
  `css/styles.css` or `js/*.js` after Step 2.

- **`file://` tests** (`test_m6_extras.js`, `verify_deltat_js.js`,
  `verify_render_perf.js`): add HTTP server via the shared helper.
  Replace `page.goto('file:///' + HTML)` with
  `page.goto('http://127.0.0.1:' + port)`.

**1e. Add npm scripts.**

```json
"scripts": {
  "build": "node scripts/bundle.js",
  "test":  "node scripts/test_m5.js && node scripts/test_m6.js && node scripts/test_f1f2.js && node scripts/test_m6_extras.js"
}
```

**Before starting**, run `test_m4.js` to determine whether it still
passes. If it fails (e.g., missing test fixtures), exclude it from
the `test` script — do not carry an uncertain baseline.

**1f. Verify.** Run `npm test` — all tests pass on the unchanged
monolith served via HTTP. Run `npm run build` — `dist/compare.html`
is produced. Open `dist/compare.html` via `file://` — works.

Record pass count as baseline. **Commit to main.**

---

### Step 2 — Extract CSS

- Copy the `<style>` block (lines 7-310) verbatim into
  `web/css/styles.css`.
- Replace the `<style>` block in `compare.html` with
  `<link rel="stylesheet" href="css/styles.css">`.
- `npm run build` now inlines the CSS back into `dist/compare.html`.

**Readiness gate:** `npm test` passes, `npm run build` produces
`dist/compare.html`, `file://` spot-check works. **Commit to main.**

---

### Step 3 — Extract `constants.js` + `calculations.js` + `validators.js`

Extract the three leaf modules that have zero DOM access and zero
internal imports. Do them together — they are independent, mechanical
extractions with no design decisions.

1. **`js/constants.js`** — cut `COLUMNS`, `SVG_W`, `PAD`, `PLOT_W`,
   `MAP_SIZE`, `MAP_PAD`, `PANEL_DEFS`, `HEATMAP_RAMPS`,
   `HEATMAP_CHANNELS`, `LAP_COLOUR_DEFAULTS`, `LAP_COLOUR_LS_KEY`,
   `ZOOM_LS_KEY`. Add `export` to each.

2. **`js/calculations.js`** — cut every pure-math function listed in
   the Module Responsibilities section. Import nothing. Add `export`.

3. **`js/validators.js`** — cut `parsePickerValue` (lines 1587-1594).
   Create `isValidHexColour(s)` as a new one-line wrapper around the
   raw `HEX_RE` regex (line 1129). Delete `const HEX_RE` from the
   inline script. (The import of `isValidHexColour` into the inline
   `loadPersistedColours` call site is wired now — don't leave a
   dangling reference to the deleted `HEX_RE`.)

The inline `<script>` gains `import { … } from './js/constants.js'`
(etc.) at the top. The bundle script (Step 1b, case 4) handles this
automatically — esbuild resolves the relative imports when producing
`dist/compare.html`.

**Shadow detection check:** For each extracted symbol `SYM`, verify the
inline `<script>` has exactly one occurrence — the `import` line. A
leftover `const SYM = ...` silently shadows the import. Use:
`grep -c 'SYM' web/compare.html` — expect 1 (the import line) plus
any legitimate _uses_ of `SYM` in the remaining inline code. The
_declaration_ must be gone.

**Readiness gate.** `npm test` + `npm run build` + `file://` check.
**Commit to main.**

---

### Step 4 — Extract `appState.js`

Move mutable runtime state into `js/appState.js`:

- `store` (Map, line 483)
- `pendingSidecars` (Map, line 1600)
- `currentSessionBins`, `currentRefBins`, `currentMaxDist`,
  `currentDtBins`, `currentTrackX`, `currentTrackZ`,
  `currentZoomRange`, `currentOverlapRange`, `trackTransform`
  (lines 1116-1124)
- `currentMapMode` (line 1190) — currently a bare `let`; export it
  with a setter so `eventHandlers.js` can update it on map-mode change
- `state` (line 1847) — the object `{maxDist, dragging, dragStartX,
  dragStartDist, currentRenderParams}`

Export getters/setters or a plain object — prefer the simplest approach
(exported `let` bindings with setter functions where mutation is needed
from outside).

Note: `storeKey` and `fileStem` are pure string helpers — they go in
`utils.js` (Step 5), not here.

**Readiness gate + commit to main.**

---

### Step 5 — Extract `utils.js`

Move pure string helpers (`storeKey`, `fileStem`), formatting helpers,
persistence helpers (`applyLapColour`, `persistLapColours`,
`loadPersistedColours`, `persistZoom`, `loadPersistedZoom`), error
display, and badge helpers (`setBadge`). `loadPersistedColours` uses
`isValidHexColour` — import it from `validators.js`.

**`persistZoom` signature change:** The monolith's `persistZoom` reads
`currentMaxDist` from module scope (line 1160). In the modular version,
add an explicit `maxDist` parameter: `persistZoom(zoom, maxDist)`. This
keeps `utils.js` independent of `appState.js`. Update the three call
sites (lines 2025, 2035, 2052) to pass `state.maxDist` (or import
`currentMaxDist` from appState at the call site).

**Readiness gate + commit to main.**

---

### Step 6 — Extract `pickers.js`

Move `rebuildPickers`, `addSessionEntry`, `refreshSessionListBadges`,
and `updateCompareBtn` into `js/pickers.js`. Imports `appState`,
`utils`, `constants`.

**Why pickers before dataTransforms:** `pickers.js` must exist before
`dataTransforms.js` is extracted, because the file-load orchestration
wrappers call `addSessionEntry`, `rebuildPickers`, and
`refreshSessionListBadges`.

**Readiness gate + commit to main.**

---

### Step 7 — Extract `dataTransforms.js` (riskiest step)

**This is the only step that changes function boundaries** rather than
just moving code. The monolith's `loadFile`, `loadDeltabestCsv`, and
`loadSidecar` interleave data parsing with DOM updates. This step
splits each into a pure-data parser (here) and a DOM-orchestration
wrapper (stays inline, moves to `eventHandlers.js` in Step 9).

Move the **pure data** functions: `fileToAsyncBuffer`, `readColumns`,
`buildSegments`, `annotateSegments`. Create three new pure-data
functions by extracting the data-only logic from the monolith's
load functions:

| New function | Extracted from | Returns |
|---|---|---|
| `parseParquetFile(file)` | `loadFile` (1730-1787) | `{key, entry, missingCols}` — does NOT touch DOM or store |
| `parseDeltabestCsv(file)` | `loadDeltabestCsv` (1607-1706) | `{key, entry}` — does NOT touch DOM or store |
| `parseSidecar(file)` | `loadSidecar` (1708-1728) | `{stem, sidecar}` — does NOT touch DOM or store |

The DOM-orchestration shells (`handleFileLoad`, `handleCsvLoad`,
`handleSidecarLoad`) stay in the inline `<script>` for now. They
call the pure parsers and then do the DOM updates (store.set,
addSessionEntry, rebuildPickers, showError, etc.).

The CDN imports (`parquetRead`, `parquetMetadataAsync`, `compressors`)
move from the inline `<script>` into `dataTransforms.js` — they are
only used by the data layer.

**Why this step deserves extra care:** The parser functions return result
objects instead of mutating DOM directly. A subtle error (e.g.,
returning the wrong shape, missing a field that a DOM wrapper expects)
won't crash but will produce wrong UI. Test every file-load path:
parquet, parquet+sidecar, CSV, multi-file, error cases.

**Readiness gate + commit to main.**

---

### Step 8 — Extract `renderer.js`

Move all SVG rendering functions (`renderPanel`, `renderDtPanel`,
`renderAll`, circuit map functions, polyline builders). Imports
`constants`, `appState`, `calculations`.

**Signature note:** Several map/circuit functions take zero arguments
and read module-scope state. In the modular version they import that
state from `appState.js` — the signatures stay parameter-free. The
only change is replacing bare `currentTrackX` with
`appState.currentTrackX` (or a destructured import).

**Readiness gate + commit to main.**

---

### Step 9 — Extract `eventHandlers.js`

Move all event-listener setup, callbacks, and the DOM-orchestration
wrappers (`handleFileLoad`, `handleCsvLoad`, `handleSidecarLoad`).
Exports `initEventHandlers()`. Imports everything it needs from the
other modules.

**Module-scope DOM lookups:** The monolith declares `plotArea`,
`cursorLine`, `tooltip` as top-level `const` via `getElementById`.
Move these inside `initEventHandlers()` as local `const` bindings
(not at the top of the module file — ESM execution order could
change with future import reordering).

**Readiness gate + commit to main.**

---

### Step 10 — Create `main.js`, finalise `compare.html`

- Write `js/main.js` as the thin boot + debug-hook entry point.
- At this point the inline `<script>` in `compare.html` should be
  empty (all code extracted). Replace it with a single
  `<script type="module" src="js/main.js"></script>`.
- Add the module-load fallback `<script>` (non-module) that detects
  failed loading and shows: *"Module loading failed. Serve this
  directory from an HTTP server: `python3 -m http.server -d web`"*.
- The file keeps its `compare.html` name.

**Readiness gate + commit to main.**

---

### Step 11 — Final regression + documentation

- Run every Playwright test. Pass count must match or exceed baseline.
- `npm run build` — verify `dist/compare.html` works via `file://`.
  Full spot-check: load session + sidecar + CSV, pick laps, compare,
  zoom, hover tooltip, change colours, reset colours, switch map mode.
- Update README and CLAUDE.md:
  - Users: *"Open `dist/compare.html` — `file://` works, no server
    needed."*
  - Development: *"`python3 -m http.server -d web 8000` serves the
    modular source. `npm run build` regenerates `dist/compare.html`."*

**Commit to main.**

---

## Incremental Delivery Properties

Each step in this plan satisfies the following invariants:

| Property | How |
|---|---|
| **Commit to main** | Every step is a self-contained commit on `main`. Revert any step independently. |
| **`web/` works via HTTP** | Playwright tests run against `web/` at every step. The inline `<script>` shrinks but always works. |
| **`dist/` works via `file://`** | `npm run build` produces a standalone `dist/compare.html` at every step. The bundle script handles both hybrid (inline script + module imports) and final (main.js entry point) states. |
| **Tests are the gate** | No step is committed unless the full Playwright suite passes. Shadow bugs caught by grep checks. |
| **Riskiest step identified** | Step 7 (dataTransforms) is the only step that changes function boundaries. All other steps are mechanical cut-paste. Step 7 can be sub-divided if it proves difficult. |
| **No broken user path** | Users who open `dist/compare.html` via `file://` are never broken. The build pipeline exists from Step 1. |

### Hybrid-state mechanics (Steps 3–9)

After cutting a symbol from the inline `<script>`, you must (a) delete
the inline declaration entirely and (b) add a corresponding `import
{ … } from './js/foo.js'` at the top of the inline block. A leftover
inline `const` that shadows the import produces zero errors but wrong
behaviour.

**Shadow detection check (run after every extraction):** For each
symbol `SYM` just moved to a module, verify the inline `<script>` has
no _declaration_ of `SYM` remaining — only the `import` line and
legitimate _uses_. Use: `grep -n 'SYM' web/compare.html` and confirm
the declaration is gone. `npm run build` + tests catch most
regressions, but shadow bugs are silent — the grep check is essential.

---

## Constraints

| Constraint | Rationale |
|-----------|-----------|
| `file://` keeps working for users | `dist/compare.html` (built via `npm run build`) is the user-facing artifact; opens with a double-click, no server needed |
| One build step, not a build system | `esbuild` (devDependency) inlines modules into a single file; no webpack/vite/rollup config |
| ESM only (`type="module"`) | Already used for CDN imports; native browser support; Electron-ready |
| Same two CDN imports | hyparquet + hyparquet-compressors, unchanged |
| No new runtime dependencies | `esbuild` is dev-only (alongside Playwright); zero-install for the browser side |
| Playwright tests unbroken | Automated gate — every existing assertion passes |
| `window.__*` debug hooks preserved | Tests call these directly |
| No behaviour change | Pixel-identical rendering, identical interactions |

---

## Risks & Mitigations

**Relative ESM imports vs `file://`.**  Relative `import './js/foo.js'`
is blocked by browser same-origin policy on `file://`. (CDN imports work
because they are cross-origin HTTPS fetches — a different mechanism.)
Mitigation: `dist/compare.html` inlines all modules at every step (the
bundle script handles both hybrid and final states). The modular
`web/compare.html` includes a fallback `<script>` (added in Step 10)
that detects failed module loading and shows a clear error.

**Bundle script must handle hybrid state.** During Steps 3–9, the
inline `<script>` contains both inline code and `import` statements
for already-extracted modules. The bundle script (Step 1b) handles
this by extracting the inline script to a temp file and running esbuild
on it. Mitigation: the bundle script is written and tested in Step 1,
before any extraction begins. Verify it after each step.

**Three `file://` test harnesses.** `test_m6_extras.js`,
`verify_deltat_js.js`, and `verify_render_perf.js` all use
`page.goto('file:///')` — no server. After the split, ESM imports
would fail silently. Mitigation: all three are converted to HTTP
servers in Step 1, before any code extraction.

**Circular imports.** The dependency graph is acyclic by design.
`renderer.js` and `eventHandlers.js` both need `appState.js`, but
neither imports the other. `renderAll` is in `renderer.js`; event
handlers call it via a direct import, not a callback.

**Shadowed declarations during hybrid steps.** Steps 3–9 leave
`compare.html` with a shrinking inline `<script>` that imports from
the new modules. A leftover `const COLUMNS = [...]` that shadows the
import produces zero errors but silently uses stale data. Mitigation:
after each extraction, delete the inline declaration, add the import,
grep for the symbol name to confirm it appears only as an import.
The readiness gate (tests + build + file:// check) catches most regressions
but shadow bugs can be subtle — the grep check is essential.

**Large `renderAll` function.** At ~190 lines it is the biggest single
function. It stays in `renderer.js` as a deliberate choice — it is a
render pipeline and splitting it would scatter the data-flow across
files with no clear boundary.

**DOM coupling in file-load functions (Step 7 — riskiest step).**
The monolith's `loadFile`, `loadDeltabestCsv`, and `loadSidecar`
interleave data parsing with DOM updates. A naive cut-paste into
`dataTransforms.js` would violate its "no DOM" contract. Mitigation:
split each into a pure-data parser in `dataTransforms.js` and a
DOM-orchestration wrapper (stays inline until Step 9). The parser
returns a result object or throws; the wrapper does try/catch and
DOM updates. This is the only step that changes function boundaries.
Test every file-load path: parquet, parquet+sidecar, CSV, multi-file,
error cases. If this step proves harder than expected, it can be
further sub-divided: extract the low-level pure functions first
(`fileToAsyncBuffer`, `readColumns`, `buildSegments`,
`annotateSegments`) and defer the parser split to a follow-up commit.

**Step ordering: pickers before dataTransforms.** The DOM-orchestration
wrappers call `addSessionEntry` and `rebuildPickers`. Mitigation:
extract `pickers.js` (Step 6) before `dataTransforms.js` (Step 7).

**Module-scope DOM lookups.** The monolith has `const plotArea =
document.getElementById(...)` at the top level. Mitigation: move
these inside `initEventHandlers()` when extracting `eventHandlers.js`
(Step 9).

**`persistZoom` reads `currentMaxDist` from scope.** Mitigation: add
an explicit `maxDist` parameter in Step 5 and update call sites.

**`dist/compare.html` staleness.** The standalone build is a derived
artifact. Mitigation: add a pre-commit hook that runs `npm run build`
and verifies `dist/compare.html` is up to date.

---

## Future: Electron

The modular `web/` layout is already Electron-ready. Electron's custom
protocol handler (`protocol.handle`) serves local files with correct
MIME types and origin, so ESM `import` works without bundling. The
Electron shell is roughly:

```js
const { app, BrowserWindow, protocol } = require('electron');
protocol.handle('app', (req) => {
  const filePath = path.join(__dirname, 'web', /* resolve URL */);
  return net.fetch('file://' + filePath);
});
mainWindow.loadURL('app://./compare.html');
```

At that point `dist/compare.html` and the bundle script become
unnecessary and can be removed.
