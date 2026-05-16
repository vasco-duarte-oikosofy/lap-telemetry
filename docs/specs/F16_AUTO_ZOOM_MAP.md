# F16: Auto-zoom map canvas to selected track segment

## Goal

When the user zooms into a distance range on a telemetry chart, the track
map canvas automatically zooms and pans to frame the corresponding track
segment. When the chart zoom is reset, the map resets to the default
full-track view.

## Current behaviour

- The user can drag-select a distance range on any telemetry panel (this
  sets `visibleRange` / `currentZoomRange`).
- With `mapLinkedHighlight` enabled, a white highlight band appears on the
  map over the selected segment — but the map itself stays at full-track
  zoom, so the highlighted portion may be tiny.
- With `mapZoomPan` enabled, the user can manually zoom/pan the map.
  There is no automatic connection between chart zoom and map zoom.

## Target behaviour

- A new feature flag `mapAutoZoom` (default: `false`) appears in the
  feature-flag dropdown.
- When `mapAutoZoom` is enabled and a `visibleRange` is present, the map
  automatically zooms and pans to frame the highlighted track segment with
  10 % padding on each side.
- When the chart zoom is cleared (double-click / Esc), the map resets to
  the default full-track view.
- `mapAutoZoom` depends on `mapLinkedHighlight` — the highlight must be
  drawn for the auto-zoom target to be defined. If `mapLinkedHighlight`
  is off, `mapAutoZoom` has no effect.
- Manual zoom/pan is still available when `mapAutoZoom` is off. When
  `mapAutoZoom` is on, auto-zoom overrides the manual transform each
  render cycle.

## Slices

### Slice 01 — Feature flag and wiring

**Outcome.** `mapAutoZoom: false` appears in the feature-flag dropdown.
Selecting it logs to console. No visual change yet.

- Add `mapAutoZoom: false` to `features` in `appState.js`.
- The existing `syncFeatureFlagMenu` in `ui.js` automatically picks it up.
- Add a `console.log('mapAutoZoom:', value)` in the flag change handler so
  the slice is testable — toggling the flag produces visible output.
- Playwright test: load page, toggle flag, verify the flag is set in
  `window.__features`.

### Slice 02 — Compute segment bounding box

**Outcome.** A new `computeSegmentBounds(lapA, visibleRange)` function
returns `{ minX, maxX, minZ, maxZ }` for the track XY coordinates within
the visible range. Testable in isolation with pure-data unit tests.

- Add `computeSegmentBounds` to `trackHeatmapMap.js` (or a new
  `trackSegmentBounds.js` if the file grows past 200 lines).
- It walks `lapA.x[startIdx..endIdx]` and `lapA.z[startIdx..endIdx]` and
  returns the axis-aligned bounding box.
- Edge cases: full-track range returns `null` (no auto-zoom needed);
  empty range returns `null`.
- Node unit test: feed synthetic data, verify bounds are correct for
  known ranges, verify `null` for full-track and empty ranges.

### Slice 03 — Auto-zoom transform when flag is on

**Outcome.** When both `mapLinkedHighlight` and `mapAutoZoom` are enabled
and a `visibleRange` is present, the map automatically frames the segment.
When the range is cleared, the map resets.

- In `trackHeatmapController.js`, after computing `buildOpts()`, if
  `mapAutoZoom` is on and `visibleRange` is present and not full-track:
  - Call `computeSegmentBounds(lapA, visibleRange)` to get the bounding box.
  - Add 10 % padding on each axis.
  - Call `fitToView` with the padded bounds (same function already used
    for the full-track view) to compute a new base transform.
  - Use `mapInteraction.setState()` to set the user transform to
    `{ scale: 1, tx: 0, ty: 0 }` — this makes the auto-zoom the default
    view, with no additional user zoom/pan on top.
  - Call `setBaseTransform(tf)` so that any user zoom/pan is relative to
    the auto-zoomed view.
- When `mapAutoZoom` is on and `visibleRange` is `null` (zoom reset):
  - Let the normal full-track `fitToView` happen (already the default).
  - Reset `mapInteraction.setState({ scale: 1, tx: 0, ty: 0 })`.
- When `mapAutoZoom` is off: do nothing (existing behaviour preserved).

### Slice 04 — Playwright acceptance test

**Outcome.** An automated test verifies that enabling `mapAutoZoom` with a
zoomed chart view causes the map to zoom in on the corresponding track
segment.

- Load a session, enable `mapLinkedHighlight` and `mapAutoZoom`.
- Use the chart zoom interaction to select a distance range.
- Read the map canvas transform (`__mapZoomPanState`) and verify `scale > 1`
  (the map has zoomed in).
- Reset chart zoom (double-click or Esc simulation).
- Verify `scale === 1` (the map has reset to full-track).

## Architecture notes

```
                        ┌──────────────────┐
                        │   appState.js     │
                        │  mapAutoZoom flag  │
                        └──────┬───────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
  ┌────────▼────────┐  ┌──────▼──────┐  ┌─────────▼──────────┐
  │ trackHeatmap     │  │ trackHeatmap │  │ trackSegmentBounds │
  │ Controller.js    │  │ Map.js       │  │ .js (new)          │
  │                  │  │              │  │                    │
  │ if autoZoom:    │  │ fitToView()  │  │ computeSegment     │
  │   compute bounds │  │ applyUser    │  │ Bounds()          │
  │   fitToView()   │  │ Transform()   │  └────────────────────┘
  │   setState()     │  └──────────────┘
  └──────────────────┘
```

The auto-zoom logic lives in `trackHeatmapController.js` — it calls
`computeSegmentBounds` to get the bounding box, then `fitToView` (already
in `trackHeatmapMap.js`) to compute the transform, and `setState` (already
on `mapInteraction`) to apply it. No new modules are needed for the core
logic; `computeSegmentBounds` may be a small function added to
`trackHeatmapMap.js` or extracted to its own file.

## Scope

- `product/web/js/appState.js` — feature flag
- `product/web/js/trackHeatmapController.js` — auto-zoom logic
- `product/web/js/trackHeatmapMap.js` — `computeSegmentBounds`
- `product/web/js/mapInteraction.js` — no changes needed (setState already
  exists)
- New Playwright test for slice 04

## Out of scope

- Changing how the chart zoom/selection works (existing).
- Replacing the map zoom/pan interaction (existing).
- Shared browser context for Playwright tests (future optimisation).
- Any changes to the linked highlight band rendering (existing).