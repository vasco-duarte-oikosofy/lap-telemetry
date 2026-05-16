# Slice 01 Handoff — Feature flag and wiring

## State on disk

- **`product/web/js/appState.js`**: Added `mapAutoZoom: false` after `mapLinkedHighlight` in the `features` object. No other changes.
- **`dev/scripts/test_f16_auto_zoom.js`**: New Playwright test file with 8 assertions covering:
  1. Flag defaults to `false`
  2. Flag appears in `window.__features`
  3. Flag can be enabled via `__setFeatureFlag`
  4. Flag can be disabled via `__setFeatureFlag`
  5. Flag toggles on via dropdown UI
  6. Flag toggles off via dropdown UI
  7. `mapAutoZoom` appears after `mapLinkedHighlight` in `Object.keys(features)`
  8. Screenshot artifact written

- **`product/dist/compare.html`**: Rebuilt and current.

## Feature flags live

- `mapAutoZoom: false` — default OFF, appears in feature-flag dropdown as `○ mapAutoZoom`

## No behavior changes

- No module reads `features.mapAutoZoom` yet. That's intentional — this slice is wiring only.
- Subsequent slices will:
  - **Slice 02**: Add `computeSegmentBounds()` to `trackHeatmapMap.js`
  - **Slice 03**: Wire auto-zoom into the render loop, gated by `features.mapAutoZoom && features.mapLinkedHighlight`

## Deferred TODOs

None. This slice is complete per acceptance criteria.