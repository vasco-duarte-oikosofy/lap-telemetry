# F1 + F2 — Circuit map + distance-range zoom + two bug fixes

**Goal:** Add a circuit map sidebar with a cursor-following dot (F1), implement click-drag distance-range zoom (F2), fix tooltip positioning (Fix 3), and stabilize Δt for pre-F4 recordings (Fix 4).

---

## Scope

### A. Circuit map SVG rendering

**Data prep:**
- Add `pos_x_m` and `pos_z_m` to the `readColumns` call.
- Verify they are in the `COLUMNS` constant in `readColumns`; if not, add them.
- After `resample()`, populate `currentSessionBins` with `trackX[bin]` and `trackZ[bin]` (Float32Array, 1 m spacing).

**SVG rendering:**
- Compute axis bounds: `min/max(trackX)` and `min/max(trackZ)` from the resampled arrays.
- Normalize to a fixed SVG viewport (e.g., 250 px wide, 250 px tall) with 20 px padding.
- Create a fixed-width `<div id="circuit-map-panel">` (250 px) next to the `#plot-area`.
- Render a `<svg>` with a `<polyline>` of all track points (connect all resampled `[trackX, trackZ]` pairs).
- SVG layout: shift `#plot-area` to flex 1 (takes available space); circuit map panel is `flex: 0 0 250px`.

### B. Cursor dot on circuit map

**Interaction:**
- Add a `<circle class="cursor-dot">` inside the circuit map SVG.
- On `mousemove` across any telemetry panel, compute the distance under the cursor via `e.clientX` → `fracX` → distance.
- Look up the resampled bin index and fetch `trackX[binIdx]` and `trackZ[binIdx]`.
- Transform to SVG pixel coordinates using the computed bounds and viewport scale.
- Update the circle's `cx` and `cy` attributes via `setAttribute`.

### C. Distance-range zoom interaction and state

**App state:**
- Add `zoomRange = { start: 0, end: maxDist }` to app state.

**Interaction flow:**
- `mousedown` on `#plot-area`: record `startDist` from cursor position.
- `mousemove` while held: draw a translucent selection rect overlay (`<div>` with `left`, `width`, `background-color: rgba(...)`)
- `mouseup`: commit zoom — update `zoomRange.start` and `zoomRange.end`; call `renderAll()` to re-render all panels with the new zoom.

**Cursor coordinate transform:**
- Modify `toX(distance, zoom)` signature: now takes `zoom = zoomRange` as a parameter.
- Maps `[zoom.start, zoom.end]` to `[PAD.left, PAD.left + PLOT_W]`.
- Update all calls to `toX()` to pass `zoomRange`.

### D. Map arc highlight

**Zoom arc on circuit map:**
- When zoom is active (`zoomRange.start > 0` or `zoomRange.end < maxDist`), filter the track polyline to only include points in `[zoomRange.start, zoomRange.end]`.
- Draw a second `<polyline class="zoom-arc">` with a highlight color (e.g., `#ffd54f` from `--sector-clr`).
- Compute polyline points: iterate `trackX/trackZ` bins from `zoomRange.start / 1` to `zoomRange.end / 1`, transform to SVG coords, build `points` string.

### E. Zoom reset

**Double-click or Escape:**
- Add a `dblclick` handler on `#plot-area`: reset `zoomRange` to `{start: 0, end: maxDist}` and call `renderAll()`.
- Add a `keydown` listener for `Escape`: same reset.

### F. Fix 3 — Tooltip follows cursor

**Current issue:** Tooltip is hardcoded at `top: 20px`.

**Fix:**
- In `mousemove` handler, replace `const ty = 20;` with:
  ```javascript
  const ty = Math.max(8, Math.min(e.clientY - rect.top - 30, rect.height - 130));
  ```
- This offsets the tooltip up by ~30 px from the cursor, clamped inside the plot area.
- Adjust offset/margins as needed for readability.

### G. Fix 4 — Δt stability for pre-F4 recordings

**Diagnosis:**
1. Load a post-F4 recording (any session file recorded after `_estimate_dist` commit).
2. Run the same comparison from M5 tests. If Δt is smooth, the bug is pre-F4 data only.
3. If still wrong on new data, the formula is broken. (Expected: bug is data-specific.)
4. Call `window.__resamplerDebug(key, segIdx)` on both laps; inspect speed bins around a braking zone (bins 900–1100) to confirm cluster-aliasing.

**Stable sort fix:**
- In `resample()`, change:
  ```javascript
  idx.sort((a, b) => distances[a] - distances[b]);
  ```
  to:
  ```javascript
  idx.sort((a, b) => (distances[a] - distances[b]) || (a - b));
  ```
- This breaks ties by original frame index, preserving time order within equal-distance clusters.

**Coarse-data warning:**
- Compute median frame-to-frame distance delta: `distances[i+1] - distances[i]` for all `i`.
- If median > 2 m, display a warning banner near the Δt panel label: "legacy distance resolution — Δt accuracy limited".
- Position the warning as a small badge or inline text (not a blocking modal).

### H. Playwright test suite

**File:** `scripts/test_f1f2.js`

**Baseline scenario:** Load clean 6-lap session and reference lap (lap 5); compare lap 4 vs lap 5 (same as M5 baseline).

**Assertions:**
1. Circuit map SVG exists (`#circuit-map-panel svg`).
2. Track outline polyline has ≥200 points.
3. On `mousemove` to panel centre, cursor dot is visible in map and has non-zero initial position.
4. Zoom interaction: drag from 20% to 60% of plot width.
   - After drag, x-axis labels show sub-range (not 0 to max).
   - Zoom-arc element present in map SVG.
   - After double-click, x-axis returns to full range.
5. Screenshots: initial load, after compare, after hover, after zoom, after reset.
6. Console log captured; any error fails test.
7. Resampler and Δt assertions from M5 tests do **not** need repeating — reference them in REPORT.md as "inherited from M5".

**Test report:** `f1f2-test-report/REPORT.md` summarizing what ran, what passed, screenshots.

### I. Gitignore

Add `f1f2-test-report/` to `.gitignore` if not already covered by the `m*-test-report/` pattern.

---

## Steps

1. **Read and verify column availability (piece A)**
   - Check `readColumns` for `pos_x_m` and `pos_z_m`.
   - If absent, add to the columns list and verify parse succeeds on test session.

2. **Resample track coordinates (piece A)**
   - Add resampling logic for `trackX` and `trackZ` (same 1 m bin approach as speed/throttle/brake).
   - Populate `currentSessionBins` object with these arrays.

3. **Compute axis bounds and normalize (piece A)**
   - Extract min/max of resampled `trackX` and `trackZ`.
   - Design SVG viewport transform (250 px × aspect ratio to match data).
   - Build the transform function: `(worldX, worldZ) → (svgX, svgY)`.

4. **Render circuit map panel (piece A)**
   - Create `<div id="circuit-map-panel">` div (250 px fixed width).
   - Render `<svg>` with a `<polyline>` connecting all resampled track points.
   - Append to `#plots` or parent container; style with `flex: 0 0 250px`.
   - Adjust `#plot-area` to `flex: 1` so it shares space with map.

5. **Add cursor dot to map (piece B)**
   - Insert `<circle class="cursor-dot" r="4" fill="currentColor">` into circuit map SVG.
   - Modify `mousemove` handler to compute distance, look up resampled `[trackX, trackZ]`, transform to SVG coords, update circle.

6. **Implement zoom state and `toX()` refactor (piece C)**
   - Add `zoomRange` to app state, initialized to `{ start: 0, end: maxDist }`.
   - Change `toX(distance)` to `toX(distance, zoom)` — map `[zoom.start, zoom.end]` to x-pixels.
   - Update all `toX()` calls in panel rendering functions to pass `zoomRange`.

7. **Add drag interaction and selection rect (piece C)**
   - Add `mousedown`, `mousemove`, `mouseup` handlers to `#plot-area`.
   - On `mousedown`: store `startDist`.
   - On `mousemove` (while held): draw a semi-transparent selection rect overlay.
   - On `mouseup`: compute `endDist`, update `zoomRange`, call `renderAll()`.

8. **Draw zoom arc on circuit map (piece D)**
   - When `zoomRange` is active, filter resampled track points to `[zoomRange.start, zoomRange.end]`.
   - Create a second `<polyline class="zoom-arc">` with highlight color and place atop the main track outline.

9. **Add zoom reset (piece E)**
   - Add `dblclick` handler: reset `zoomRange` to `{start: 0, end: maxDist}`, call `renderAll()`.
   - Add `keydown` listener for `Escape`: same reset.

10. **Fix tooltip Y positioning (piece F)**
    - Locate the hardcoded `ty = 20` in the `mousemove` handler.
    - Replace with dynamic clamping: `const ty = Math.max(8, Math.min(e.clientY - rect.top - 30, rect.height - 130));`

11. **Fix Δt resampler stability (piece G)**
    - **Diagnosis phase:** Load a post-F4 session, run same M5 comparison, verify Δt is smooth (confirms bug is data-specific).
    - **Stable sort:** Change sort comparator in `resample()` to break ties by frame index.
    - **Coarse-data warning:** Compute median distance delta; if > 2 m, display inline warning badge.

12. **Write Playwright test suite (piece H)**
    - Copy and extend M5 test structure.
    - Add circuit map, cursor dot, zoom interaction, and reset assertions.
    - Generate screenshots and REPORT.md.
    - Ensure all M5 tests still pass (inheritance note in REPORT).

13. **Update `.gitignore`** if needed.

14. **Run smoke test:** `lap-telemetry summary sessions/<latest>` (unchanged).

15. **Commit.**

---

## Acceptance tests

| ID  | Test |
|-----|------|
| T1  | Circuit map SVG renders with ≥200-point track polyline. |
| T2  | Cursor dot visible on map; position changes on `mousemove` across panels. |
| T3  | Zoom drag (20% → 60%) changes x-axis labels to sub-range; zoom arc visible on map. |
| T4  | Double-click or Escape resets zoom; x-axis returns to full range. |
| T5  | Fix 3: Tooltip follows cursor vertically, clamped inside plot area. |
| T6  | Fix 4 (diagnosis): Post-F4 recording has smooth Δt; pre-F4 has expected oscillation (stable sort applied). |
| T7  | Coarse-data warning displays when median frame-distance > 2 m. |
| T8  | All 7 M5 panels still render correctly with zoom applied. |
| T9  | Playwright test suite: circuit map, cursor, zoom, reset, screenshot assertions pass. |
| T10 | Console log captured; no errors. |
| T11 | M5 smoke test still passes (unchanged). |

---

## Notes

- **Layout trade-off:** 250 px fixed-width circuit map + flexible plot area = ~28% map width (lower bound from handoff, acceptable). If space becomes tight, can move map above/below panels instead (document in this plan).
- **Zoom persistence:** No localStorage; reset on page reload (M6 feature).
- **Zoom arc color:** Using `--sector-clr` (#ffd54f); adjust if contrast is poor.
- **Δt warning placement:** Inline badge next to "Δt" panel label, not a modal.
- **Post-implementation:** Update `DESIGN.md` §11 to mark F1 and F2 as shipped; update `CLAUDE.md` "Current state".
