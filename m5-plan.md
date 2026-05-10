# M5 — Full plot stack + unified loading

**Goal:** Extend `web/compare.html` with a complete multi-panel telemetry
overlay and replace M4's two-upload flow with a unified session loader where
the user picks both laps from the same (or different) loaded session files.

---

## Scope

### A. Unified loading

**Problem with M4.** The user must pre-slice a reference lap with
`scripts/extract_reference_lap.py` and load two separate parquet files. This
is friction: every time they pick a new reference they have to re-run the
script. The two-upload flow also makes it impossible to compare two laps from
the same session.

**New flow.** Replace the two `<input type="file">` cards with a **session
library** panel:
- Single file-input button to load/add session files. Multiple files can be
  loaded (one button, multiple parquet drops). Each loaded file becomes one
  entry in a list (filename, row count, lap count, status badge).
- Two pickers: **"Session lap"** and **"Reference lap"**. Each picker shows
  all laps from all loaded files, formatted as
  `<file_stem> / Lap N (lap# M) — duration`. Laps are grouped by file in the
  drop-down. The two pickers can select the same file or different files.
- Compare button enabled when both picks are valid. Plot renders on Compare.

**Backward compatibility.** The existing two-file-input HTML structure in M4
is replaced entirely; the page is not intended to be backward-compatible at
the URL level (the user opens the file fresh each time).

**M5 limitation to document for M6.** File paths are not persisted (no
`FileSystemFileHandle` yet). The user must reload files every time they open
the app. M6 note: use `window.showOpenFilePicker` (Chrome 86+, no Safari) or
`localStorage` for MRU list.

### B. Full plot stack

Seven panels stacked vertically, all sharing the same lap-distance x-axis:

| Panel | Traces | Y range |
|---|---|---|
| **Speed** | speed_kph (session, ref) | 0 – max + margin |
| **Throttle / Brake** | throttle_norm (green, ref dashed), brake_norm (red, ref dashed) | 0 – 1 |
| **RPM** | engine_rpm (session, ref) | 0 – max + margin |
| **Gear** | gear (session, ref) as step-plot | -1 – max gear |
| **Steering** | steering_norm (session, ref) | –1 – +1, zero-line |
| **Slip angle FL/FR** | slip_angle_fl_deg, slip_angle_fr_deg (session, ref each 4 traces) | auto |
| **Δt** | cumulative time delta (session minus ref), positive = session slower | auto, zero-line |

The Δt panel is computed by integrating `1/speed` over distance bins for each
lap and subtracting: `dt[i] = sum(1/speed_session[0..i]) - sum(1/speed_ref[0..i])`.
Positive Δt = session is losing time to reference at that point.

Panels rendered in order (Speed first, Δt last). Each panel is a separate
`<svg>` element sharing the same x-axis scale, so zoom + cursor events sync
automatically (see piece D).

**Columns required from parquet.** For M5 the app reads:
`lap_number`, `lap_time_s`, `lap_distance_m`, `speed_kph`,
`throttle_norm`, `brake_norm`, `engine_rpm`, `gear`,
`steering_norm`, `slip_angle_fl_deg`, `slip_angle_fr_deg`.

The parquet already has all of these (from M3 schema). Slip columns may be
absent in very old recordings; display "-" trace (flat at 0) in that case.

### C. Synced cursor

A vertical hairline that follows the mouse across all panels simultaneously.
- Single `mousemove` listener on a transparent overlay `<div>` spanning the
  full plot area (all panels stacked). The x position is translated to
  distance and then to x pixels in each panel's coordinate system.
- Display a tooltip with the distance and the two laps' values for each
  channel at that cursor position.
- No shared DOM between panels needed — the overlay div sets a CSS custom
  property `--cursor-x: Npx` and each panel has an `<line>` element that
  reads it via `style.left` or an attribute update in `requestAnimationFrame`.

Implementation note: use a single `requestAnimationFrame` loop per
`mousemove` to avoid layout thrashing when updating 7 cursor lines.

### D. Lap filter

In the lap picker, annotate each entry with `(out)` / `(in)` for the first
and last segment. These can still be picked but are de-emphasised (lighter
color in the option). A future M6 "hide out/in" checkbox can be added.

### E. Sector markers

Derive S1/S2 sector boundaries from the loaded data:
- Find `last_sector_1_s` (S1 duration) and `last_sector_2_s` (cumulative
  through S2) from the first settled frame of the next segment (same O1/O2
  walk as summary.py). This gives split times.
- Convert split times to distances by finding the closest frame in the
  session where `lap_time_s ≈ s1` and `lap_time_s ≈ cum_s2`.
- Draw vertical dashed lines on all panels at S1 and S2 distances, labelled
  "S2" and "S3" (the sector number the line begins).
- If no sector data is available for a lap, skip markers silently.

---

## Steps

1. **Unified loader panel (piece A)**
   a. Replace the two file-card divs with a single loader panel: file input
      button + scrollable session library list + status per file.
   b. `SessionStore` class: Map from file path (name + size) to loaded data
      `{ fileName, segments, distances, speeds, throttle, brake, rpm, gear,
        steering, slipFL, slipFR, lapTimes, lapNumbers }`.
   c. `LapPicker` component: builds `<optgroup>` per file, `<option>` per
      segment. Exposed as `getPick()` → `{ store, segIdx }`.
   d. Wire Compare button to `SessionStore.getSegment(pick)`.

2. **Expanded `readColumns` call (piece B)**
   - Add the new column names to the `columns` array in the file-load path.
   - Handle missing columns gracefully (check schema via `parquetMetadataAsync`
     before reading, or catch per-column absence in `onChunk`).

3. **Multi-panel SVG layout (piece B)**
   - Wrap all panels in a `<div id="plot-area">`.
   - `PANEL_DEFS` array: `{ id, label, channels, yRange, yStep, zeroline }`.
   - `renderPanel(panelDef, sessionBins, refBins, maxDist)` → builds one
     `<svg>` with the polylines and axes for that panel.
   - `renderAllPanels(sessionSeg, refSeg)` — calls `renderPanel` for each def
     and appends to `#plot-area`.
   - Speed panel reuses M4's existing SVG renderer (refactor, don't duplicate).

4. **Δt computation (piece B)**
   - `computeDeltaT(sessionBins, refBins)` — returns Float64Array.
   - `cumSum[i] = cumSum[i-1] + (1/sessionBins[i] - 1/refBins[i]) * 1000`
     (ms per metre, summed; multiply by bin width = 1 m). Guard against
     division by zero (speed = 0 during standing starts: use `max(speed, 1)`.

5. **Synced cursor (piece C)**
   - Overlay `<div>` with `position: absolute; inset: 0; pointer-events: none`.
   - `mousemove` on the `#plot-area` parent: compute distance from x offset,
     update each `<line class="cursor">` `x1`/`x2` via `setAttribute`.
   - Tooltip: `<div id="cursor-tooltip">` follows cursor; updated in same
     `mousemove` handler via `requestAnimationFrame`.

6. **Sector markers (piece E)**
   - `deriveSectorDistances(seg)` — walks forward from the next segment's
     start up to 25 frames (mirroring O1/O2 fix) to find `last_sector_1_s`
     and `last_sector_2_s`. Converts to distances via `lap_distance_m` array
     (find index where `lap_time_s` crosses the split time).
   - `addSectorMarkers(svg, s1dist, s2dist, toX)` — appends two `<line>` +
     `<text>` elements to the given panel SVG.
   - Called after each panel is rendered, if sector data is available.

7. **Playwright test extension (test_m5.js)**
   - Copy and extend `test_m4.js` for M5. Additional assertions:
     - All 7 panel SVGs exist and have ≥2 polylines each.
     - Δt panel exists and the polyline is present.
     - Cursor tooltip appears on `mousemove`.
     - Sector marker lines appear if session lap has sectors.
   - One new fixture test: load two laps from the SAME file (lap 3 vs lap 5
     from the clean session) using the unified picker.
   - Resampler cross-check extended to Δt: Python equivalent of
     `computeDeltaT` compared against browser output via `window.__dtDebug()`.

8. **Update `.gitignore`** to exclude `m5-test-report/`.

9. **Run smoke test:** `lap-telemetry summary sessions/session_20260510T093245Z_*` (unchanged).

10. **Commit.**

---

## Acceptance tests

| ID  | Test |
|-----|------|
| T1  | Unified picker: loading one session file populates both "session lap" and "reference lap" pickers with correct options (same count as M4 had). |
| T2  | Loading two different session files: combined lap count visible in both pickers (grouped by file). |
| T3  | All 7 panels render (Speed, Throttle/Brake, RPM, Gear, Steering, Slip, Δt) with 2 polylines each. |
| T4  | Δt panel: polyline exists; value at distance 0 is ≈ 0; Python cross-check: `max|browser_Δt − python_Δt| < 5 ms`. |
| T5  | Cursor hairline appears on `mousemove` across all panels simultaneously. |
| T6  | Sector markers appear on Speed panel when session lap has sector data (clean 6-lap session). |
| T7  | Same-file comparison: picking lap 3 vs lap 5 from the clean session works without errors. |
| T8  | `lap-telemetry summary` smoke test still passes (summary.py unchanged in M5). |
| T9  | No browser console errors across all Playwright scenarios. |

---

## Notes for M6

- Sector markers: derive distance from `lap_time_s` crossings — approximation only. Proper sector distance requires the sim to expose `mSector` or similar (not in current schema). Flag this clearly in the UI.
- Gear panel as a step-function plot: use `stroke-linejoin: miter` and horizontal/vertical segments rather than interpolated polyline (gear is an integer signal, interpolation is misleading).
- Export to JSON / clipboard for sharing a trace outside the app.
- `FileSystemFileHandle` (Chrome 86+) for persisting last-used file path between sessions — reduces friction when reopening the app.
- Lap invalidation badges in the picker (visual indicator for `lap_valid: false`).
- Zoom: linked x-axis zoom across all panels via pointer events + transform.
