# Slice 03 Handoff — Auto-zoom transform

## State on disk

- **`product/web/js/trackHeatmapController.js`** (170 lines): Three changes:
  1. Added `computeSegmentBounds` to the import from `./trackHeatmapMap.js`.
  2. Added `mapInteraction` creation block for `mapAutoZoom` (no zoom indicator).
  3. Added auto-zoom logic after `renderWalkingSkeleton()` — calls
     `computeSegmentBounds`, applies padded bounds to `fitToView`, sets
     base transform and resets user transform.
- **`product/dist/compare.html`**: Rebuilt and current.

## How to see auto-zoom in the browser

1. Open `product/dist/compare.html` (or `product/web/compare.html` with a local server).
2. Load a session file.
3. Select two laps in the pickers.
4. Enable **both** `mapLinkedHighlight` and `mapAutoZoom` in the feature-flag dropdown.
5. Zoom into a distance range on any telemetry chart (drag-select).
6. The map canvas should automatically zoom and pan to frame that segment with 10% padding.
7. Reset the chart zoom (double-click or Esc) — the map should return to full-track view.

## Behaviour matrix

| mapAutoZoom | mapZoomPan | visibleRange | Result |
|---|---|---|---|
| off | off | any | No change (existing behaviour) |
| off | on | any | Existing manual zoom/pan only |
| on | off | null/full-track | Map at default full-track view |
| on | off | partial range | Map auto-zooms to segment |
| on | on | null/full-track | Map at full-track, manual zoom available |
| on | on | partial range | Map auto-zooms to segment (overrides full-track base) |

## Key implementation detail

When both `mapZoomPan` and `mapAutoZoom` are on, both blocks run. The
`mapZoomPan` block sets the full-track base transform. Then the
`mapAutoZoom` block overrides it with the segment base transform if a
visible range is present. This ordering is correct — auto-zoom takes
precedence when a segment is highlighted.

## Deferred TODOs

None. This slice is complete per acceptance criteria. Slice 04 will add
the Playwright acceptance test.