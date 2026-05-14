# Handoff — Phase 04 Apex Metrics One Corner

State on disk:

- `web/js/apexMetrics.js`
  - Added `computeApexMetricForLap(data, corner, opts = {})`.
  - Selects samples by inclusive `raw_lap_distance_m` corner window.
  - Chooses the selected sample closest to `corner.apex_s_m`.
  - Computes `apex_timing_error_m = sample_s_m - corner.apex_s_m`.
  - Uses `distance_to_track_edge_m` at the selected sample when available.
  - Falls back to `track_edge_m - abs(path_lateral_m)` only when both fields exist at the selected sample.
  - Returns null computed metric fields for missing `raw_lap_distance_m`, missing edge-distance inputs, or no in-window sample.
  - Does not fall back to `lap_distance_m`.
  - Leaves `surface_type` and `terrain_name` as `null` for Phase 04.
- `scripts/test_apex_metrics.js`
  - Covers closest-sample selection, late/early timing signs, selected-sample edge distance, derived distance fallback, missing raw distance, missing edge inputs, and empty corner windows.
- `package.json`
  - Includes the Phase 04 metric test in `npm test`.
- `web/js/appState.js`
  - Added `features.apexMetrics`, default `false`.
- `dist/compare.html`
  - Rebuilt with `npm run build`.
- `phases_track_outline/PLAN`
  - Marks `04-apex-metrics-one-corner` DONE.
- `phases_track_outline/CURRENT`
  - Set to `04.1-apex-metrics-all-corners`.

Verification:

- `npm test` passed.
- `npm run build` passed.

Feature flags live:

- `features.apexAnnotations`: present from Phase 03, default `false`.
- `features.apexMetrics`: present from Phase 04, default `false`; not wired to UI behavior.

Deferred to Phase 04.1:

- Aggregate metrics across all laps and all configured corners.
- Define empty/status results for no annotations and no compatible telemetry.
