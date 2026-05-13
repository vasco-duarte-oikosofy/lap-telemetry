# lap-telemetry — Rendering Design

**Status:** Documented 2026-05-13 (Step 8 refactor + contextual Y-axis fix)  
**Scope:** How the comparison app (`web/compare.html`) renders telemetry panels and the circuit map.

---

## 1. Architecture Overview

The rendering layer is split into focused modules:

```
┌─────────────────────────────────────────────────────────────────┐
│  main.js — App entry point                                      │
│  • DOM event handlers (pickers, file loading, drag-reorder)     │
│  • renderAll() orchestration                                    │
│  • Debug hooks (__resamplerDebug, __dtDebug, etc.)              │
└─────────────────────────────────────────────────────────────────┘
         │
         ├─► pipeline.js — Data transforms
         │   • readColumns, resample, computeDeltaT
         │   • niceRange, computeNiceYTicks, buildPolylinePts
         │
         ├─► panels.js — Telemetry panel SVG rendering
         │   • renderPanel() — Speed, Throttle, Brake, etc.
         │   • renderDtPanel() — Δt panel with overlap clipping
         │
         ├─► circuitMap.js — Circuit map rendering
         │   • renderCircuitMap() — Outline or heatmap modes
         │   • renderHeatmapSegments(), renderMapLegend()
         │   • updateZoomArc() — Zoom range indicator
         │
         ├─► constants.js — Shared layout constants
         │   • SVG_W, PAD, PLOT_W
         │
         └─► appState.js — Global state
             • store, panelOrder, getCurrentMapMode
```

**Key principle:** Rendering functions are **pure** — they take state as parameters and return SVG strings. No module-scope dependencies on `main.js` variables.

---

## 2. SVG Layout Constants

All panels and the circuit map share a common coordinate system:

```javascript
// constants.js
export const SVG_W = 900;           // SVG viewBox width
export const PAD = { top: 6, right: 20, bottom: 24, left: 58 };
export const PLOT_W = SVG_W - PAD.left - PAD.right;  // 822 px
```

**Coordinate system:**
- X-axis: `PAD.left` to `PAD.left + PLOT_W` (data plot area)
- Y-axis: `PAD.top` to `PAD.top + plotH` (panel-specific height)
- Left padding (58 px) reserved for Y-axis tick labels
- Bottom padding (24 px) reserved for X-axis labels and axis title

---

## 3. Panel Rendering (`panels.js`)

### 3.1 `renderPanel(def, bins, maxDist, sectorDists, zoomRange)`

Renders standard telemetry panels: Speed, Throttle, TC, Brake, ABS, RPM, Gear, Steering, Slip.

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `def` | `Object` | Panel definition from `PANEL_DEFS` |
| `bins` | `Object` | Map of `trace_col` → `Float64Array` (resampled values) |
| `maxDist` | `number` | Lap length in metres (ceiling) |
| `sectorDists` | `Object` | `{ s1dist, s2dist }` sector boundary distances |
| `zoomRange` | `Object` | `{ start, end }` visible distance window |

**Key behaviors:**

1. **Contextual Y-axis scaling:** Y-axis range is computed from values **within the zoom range only**. This ensures zoomed-in sections show meaningful variation rather than being compressed by the full-lap range.

```javascript
const zoomStart = Math.ceil(zoomRange.start);
const zoomEnd = Math.floor(zoomRange.end);
const allVals = [];
for (const { key } of Object.values(bins)) {
  if (key) {
    for (let i = zoomStart; i <= zoomEnd && i < key.length; i++) {
      const v = key[i];
      if (isFinite(v)) allVals.push(v);
    }
  }
}
const [yMin, yMax] = niceRange(allVals, def.yFixed);
```

2. **X-axis transformation:** Maps distance to SVG X coordinate, respecting zoom:

```javascript
const toX = d => {
  const zRange = zoomRange.end - zoomRange.start;
  if (zRange <= 0) return PAD.left;
  const fracD = (d - zoomRange.start) / zRange;
  return PAD.left + fracD * PLOT_W;
};
```

3. **Channel rendering:** Each channel in `def.channels` is rendered as a `<polyline>`. Session traces are solid; reference traces are dashed.

4. **Activity strips:** For Brake (ABS) and Throttle (TC) panels, a 4 px coloured bar at the bottom shows when ABS/TC was active.

5. **Sector markers:** Vertical dashed lines at S2/S3 boundaries with labels.

### 3.2 `renderDtPanel(def, dtBins, maxDist, sectorDists, zoomRange, overlapRange)`

Renders the Δt (delta-time) panel.

**Key behaviors:**

1. **Overlap clipping:** Only renders the distance window where **both** laps have real data. Bins outside the overlap carry the resampler's boundary clamp, not real values.

```javascript
const overlapStart = Math.max(0, Math.ceil(overlapRange.start));
const overlapEnd = Math.min(maxDist, Math.floor(overlapRange.end));
```

2. **Contextual Y-axis scaling:** Y-axis range is computed from values within **both** the overlap AND zoom ranges:

```javascript
const zoomStart = Math.ceil(zoomRange.start);
const zoomEnd = Math.floor(zoomRange.end);
const rangeStart = Math.max(overlapStart, zoomStart);
const rangeEnd = Math.min(overlapEnd, zoomEnd);

const inRangeVals = [];
for (let i = rangeStart; i <= rangeEnd; i++) {
  if (isFinite(dtBins[i])) inRangeVals.push(dtBins[i]);
}
const [yMin, yMax] = niceRange(inRangeVals, def.yFixed);
```

3. **Sector Δt readouts:** Shows instantaneous Δt at S2/S3 boundaries and the lap-end value.

4. **Reference baseline:** Orange dashed line at y=0 (reference lap baseline).

---

## 4. Circuit Map Rendering (`circuitMap.js`)

### 4.1 `renderCircuitMap(currentTrackX, currentTrackZ, trackTransform, currentZoomRange, currentMaxDist, currentSessionBins)`

Renders the circuit map sidebar (outline or heatmap mode).

**Modes:**
- `outline`: Single polyline showing track shape
- `speed`, `brake`, `throttle`: Heatmap with colour-coded segments

**Key behaviors:**
- Track outline drawn from resampled `(pos_x_m, pos_z_m)` coordinates
- Heatmap segments drawn as 2 m coloured line segments
- Zoom arc indicator shows selected distance range on the track

### 4.2 Heatmap colour ramps

```javascript
export const HEATMAP_RAMPS = {
  speed:    v => `hsl(${(220 - 220 * v).toFixed(0)}, 85%, 55%)`,  // blue→red
  brake:    v => `rgba(244, 67, 54, ${(0.15 + 0.85 * v).toFixed(2)})`,  // grey→red
  throttle: v => `rgba(76, 175, 80, ${(0.15 + 0.85 * v).toFixed(2)})`,  // grey→green
};
```

---

## 5. Data Flow

```
User clicks "Compare"
        │
        ▼
┌─────────────────────────────────────┐
│  renderAll(session, segIdx, ref, segIdx)  │
└─────────────────────────────────────┘
        │
        ├─► computeKeepIndices() — drop boundary-artifact frames
        │
        ├─► resample() — 1 m bin grid for all channels
        │     ├─► currentSessionBins[col]
        │     └─► currentRefBins[col]
        │
        ├─► computeDeltaT() — Δt = session_lap_time - ref_lap_time
        │
        ├─► deriveSectorDistances() — S1/S2 from sector columns
        │
        ├─► renderPanel() × N panels
        │     └─► SVG string → innerHTML
        │
        ├─► renderDtPanel()
        │     └─► SVG string → innerHTML
        │
        └─► renderCircuitMap()
              └─► SVG attributes + innerHTML
```

---

## 6. Zoom Interaction

**State:** `currentZoomRange = { start, end }` persisted in `localStorage`.

**Interaction:**
1. `mousedown` on plot area: start drag, record start distance
2. `mousemove`: draw translucent selection rect
3. `mouseup`: commit zoom, re-render all panels with new `zoomRange`
4. `dblclick` or `Escape`: reset to full lap

**Re-render strategy:** All panels are pure functions of their bin data + zoom range. On zoom change, `renderAll` is called again — fast enough for interactive use.

---

## 7. Panel Definitions

`PANEL_DEFS` in `main.js` defines the panel stack:

```javascript
const PANEL_DEFS = [
  { id: 'speed',    label: 'Speed (km/h)', height: 140,
    channels: [
      { col: 'speed_kph', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'speed_kph', trace: 'ref',     color: 'var(--ref)',     dash: true  },
    ],
    yFixed: null, yStep: 50, zeroline: false },

  { id: 'throttle', label: 'Throttle', height: 60,
    channels: [ /* session + ref */ ],
    yFixed: [0, 1], yStep: 0.5, zeroline: false,
    activityStrip: { col: 'tc_active', color: 'var(--throttle)' } },

  // ... more panels

  { id: 'dt', label: 'Δt (ms, +session slower)', height: 100,
    channels: null,  // special: computed from lap_time_s traces
    yFixed: null, yStep: 100, zeroline: true, niceSteps: [1,2,5,10,25,50,100,250,500,1000] },
];
```

**Panel order:** Persisted in `localStorage` under `lap-telemetry.panel-order.v1`. User can reorder via drag-and-drop on the `⠿` grip handle.

---

## 8. Y-Axis Tick Generation

Two strategies:

### 8.1 Fixed-step panels (`yStep`)

For panels with predictable ranges (Throttle, Brake, Steering):

```javascript
const yTicks = [];
const step = def.yStep;
for (let y = Math.ceil(yMin / step) * step; y <= yMax; y += step) {
  yTicks.push(y);
}
```

### 8.2 Nice-step panels (`niceSteps`)

For panels with variable ranges (Δt, Slip):

```javascript
const yTicks = computeNiceYTicks(yMin, yMax, plotH, def.niceSteps);
// Picks smallest step from niceSteps that produces 3-5 labels with ≥30px gap
```

---

## 9. Special Cases

### 9.1 Empty channel suppression

When a channel has no data (e.g., deltabest CSV's unused channels), the polyline is suppressed to avoid misleading flat lines at y=0:

```javascript
const hasData = binArr.some && binArr.some(v => v !== 0 && isFinite(v));
if (hasData) {
  // render polyline
}
```

### 9.2 Absent panels (ABS, TC)

ABS and TC panels are not added to the DOM when the session has no ABS/TC data (pre-M6 parquet or rF2 session). The 4 px activity strips on Brake/Throttle panels remain.

### 9.3 Slip placeholder

When slip angle data is missing, a placeholder message is shown instead of an empty panel.

---

## 10. Performance Notes

- **Re-render cost:** ~31 ms resampling + ~70 ms SVG build/paint for 10 panels on a 25k-row session
- **Optimization opportunity:** Cache resampled bins per `(storeKey, segIdx, col)` to skip resampling on repeat compares
- **Current strategy:** Accept the one-time cost; subsequent compares are same-lap so user doesn't notice

---

## 11. Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `main.js` | App entry, DOM orchestration, event handlers, `renderAll` |
| `panels.js` | Panel SVG generation (pure functions) |
| `circuitMap.js` | Circuit map SVG generation (pure functions + DOM updates) |
| `pipeline.js` | Data transforms (resample, Δt, geometry helpers) |
| `constants.js` | Shared layout constants |
| `appState.js` | Global state (`store`, `panelOrder`, map mode) |
| `utils.js` | String helpers, formatting, localStorage persistence |

---

## 12. Future Improvements

- **Progressive render:** Yield between panels with `await` so UI doesn't freeze
- **Bin caching:** Cache resampled bins per lap to skip recomputation
- **Vertical zoom:** Independent Y-axis zoom per panel (deferred)
- **Map expansion:** Larger map when heatmap overlay is active (U2)
