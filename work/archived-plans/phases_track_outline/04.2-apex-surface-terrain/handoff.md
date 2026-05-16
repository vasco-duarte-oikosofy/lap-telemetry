# Handoff — Phase 04.2 Apex Surface/Terrain

State on disk:

- `web/js/apexMetrics.js`
  - `computeApexMetricForLap(data, corner, opts = {})` now fills `surface_type` and `terrain_name` from the selected apex sample when apex-side wheel channels exist.
  - `apex_side: "right"` reads front-right first, then falls back to rear-right.
  - `apex_side: "left"` reads front-left first, then falls back to rear-left.
  - Missing apex-side surface/terrain values return `null` without changing `apex_distance_m`, `apex_timing_error_m`, or `sample_s_m`.
  - Existing raw-distance and edge-distance unavailable behavior is unchanged.
- `scripts/test_apex_metrics_surface_terrain.js`
  - Covers right-front selection, left-front selection, front-to-rear fallback, and missing side data.
- `package.json`
  - Includes the Phase 04.2 test in `npm test`.
- `phases_track_outline/PLAN`
  - Marks `04.2-apex-surface-terrain` DONE.
- `phases_track_outline/CURRENT`
  - Set to `05-apex-metrics-ui`.
- `dist/compare.html`
  - Rebuilt with `npm run build`; no committed diff was produced because apex metrics are still not imported by the UI bundle.

Verification:

- `npm test` passed.
- `npm run build` passed.

Feature flags live:

- `features.apexAnnotations`: default `false`, not wired to UI behavior.
- `features.apexMetrics`: default `false`, not wired to UI behavior.

Deferred to Phase 05:

- Render text-only apex metrics UI.
- Format numeric surface types or terrain names for display if needed.
