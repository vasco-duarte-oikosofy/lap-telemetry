# Mission: F16 — Auto-zoom map canvas to selected track segment

**Spec:** [`docs/specs/F16_AUTO_ZOOM_MAP.md`](../../docs/specs/F16_AUTO_ZOOM_MAP.md)

**Goal:** When the user zooms into a distance range on a telemetry chart, the track map canvas automatically zooms and pans to frame the corresponding track segment. When the chart zoom is reset, the map resets to the default full-track view.

**Status:** 🔲 Planning

---

## Vertical slices

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-feature-flag-and-wiring` | 🔲 Not started | `mapAutoZoom: false` flag in dropdown, toggling logs to console; Playwright test verifies flag state |
| `02-compute-segment-bounds` | 🔲 Not started | `computeSegmentBounds()` returns bounding box for visible range; Node unit tests for edge cases |
| `03-auto-zoom-transform` | 🔲 Not started | Map auto-zooms to segment when flag + highlight are on, resets on zoom clear |
| `04-playwright-acceptance-test` | 🔲 Not started | Playwright test verifies auto-zoom behaviour; trials `domcontentloaded` + batched evaluate optimisation patterns|

---

## Context

- Feature flags are managed in `product/web/js/appState.js` and auto-synced to the dropdown via `syncFeatureFlagMenu` in `ui.js`.
- The map canvas is rendered by `trackHeatmapController.js` → `trackHeatmapMap.js` using `fitToView()` and `applyUserTransform()`.
- The linked highlight band is drawn by `drawLinkedHighlight()` in `trackHeatmapDrawing.js` when `mapLinkedHighlight` is on and `visibleRange` is present.
- `mapInteraction.js` provides `setState({ scale, tx, ty })` for programmatic zoom/pan control.
- `currentZoomRange` (renamed `visibleRange` in map context) is computed in `main.js` and passed through the controller.