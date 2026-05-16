# Slice 04 — Learnings

## Debug hooks for testing

- `__setZoomRange(start, end)` and `__clearZoomRange()` were added to `main.js` to allow Playwright tests to set/zoom range programmatically. Without these, we'd need fragile drag-select on panels (per L1/L3).
- `__setZoomRange` sets `currentZoomRange` and calls `renderTrackHeatmapMap()`. It does NOT call `renderAll()` — only the map re-renders. This is sufficient for auto-zoom testing since auto-zoom only affects the canvas map.
- `__getZoomRange()` returns the current `currentZoomRange` for assertions.
- `__computeSegmentBounds(lapA, visibleRange)` wraps the pipeline function for test access.
- `mapAutoZoom` was added to the `__setFeatureFlag` re-render list in `debugHooks.js` — toggling it now triggers `renderTrackHeatmapMap()`.

## Session loading flow

- File upload via `#file-input` stores data but does NOT call `renderAll()`. The user must select from pickers and click Compare (or auto-compare triggers). Tests must `dispatchEvent(new Event('change'))` on pickers, then wait for panels and zoom range.
- `__getSessionKeys()` returning data ≠ `renderAll()` having been called. Wait for `__getZoomRange() !== null` to confirm render completed.

## Canvas pixel testing

- Headless Chromium canvas renders correctly but the default viewport (1280×720) makes the canvas small (300×150). A 5×5 pixel grid over the canvas is sufficient to detect auto-zoom changes.
- Auto-zoom with range 300–700 on Barcelona data changes only ~2/25 pixels. This is because Bug 7 (`computeSegmentBounds` uses X coordinates as distance) causes the bounds to be nearly as small as the full track in some dimensions. The test asserts "at least some pixels changed" which is correct regardless of the bug.
- SC3 (clear zoom) uses 80% pixel match threshold to allow for minor rendering differences (anti-aliasing floating-point).

## __mapZoomPanState availability

- `__mapZoomPanState` only exists when `mapZoomPan` is enabled (it's set in `createMapInteraction`). When `mapZoomPan` is off, accessing it returns `undefined`. Tests that check scale/pan must enable `mapZoomPan` first.

## computeSegmentBounds and Bug 7

- `computeSegmentBounds(lapA, range)` uses `lapA.x[i]` as both the distance filter AND the X coordinate. For the test, we pass raw `pos_x_m` as `x`, which means the bounds are filtered by X position (not distance). This is Bug 7, but the test only validates determinism (same range → same bounds twice), which is correct.