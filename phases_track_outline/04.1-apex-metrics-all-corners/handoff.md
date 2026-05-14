# Handoff — Phase 04.1 Apex Metrics All Corners

State on disk:

- `web/js/apexMetrics.js`
  - Existing `computeApexMetricForLap(data, corner, opts = {})` remains the one-lap/one-corner helper from Phase 04.
  - Added `computeApexMetricsForSession(entry, annotationInput)`.
  - Accepts the loaded-session entry shape: `{ data, segments }`.
  - Accepts either a Phase 03 loader-style result (`{ status: 'ok', annotations }`) or a validated annotations object directly.
  - Preserves stable ordering by iterating `entry.segments` first, then `annotations.corners` in file order.
  - Returns `{ status: 'ok', metrics, reason: null }` for compatible configured telemetry.
  - Returns `{ status: 'not_configured', metrics: [], reason: null }` for missing/not-configured annotations.
  - Returns `{ status: 'unavailable', metrics: [], reason }` for legacy/missing telemetry:
    - missing `raw_lap_distance_m`
    - missing both `distance_to_track_edge_m` and the derivation pair `path_lateral_m` + `track_edge_m`
  - Still does not fall back to `lap_distance_m`.
  - Still leaves `surface_type` and `terrain_name` as `null`; Phase 04.2 owns those fields.
- `scripts/test_apex_metrics_aggregate.js`
  - Covers one metric per `(lap, corner)` pair.
  - Covers stable lap-then-corner ordering.
  - Verifies selected samples and early/late timing from the Phase 04 helper across multiple laps/corners.
  - Covers direct annotation object input.
  - Covers `not_configured` empty state.
  - Covers legacy raw-distance and edge-distance unavailable states.
- `package.json`
  - Includes the Phase 04.1 aggregator test in `npm test`.
- `phases_track_outline/PLAN`
  - Marks `04.1-apex-metrics-all-corners` DONE.
- `phases_track_outline/CURRENT`
  - Set to `04.2-apex-surface-terrain`.

Verification:

- `npm test` passed.
- `npm run build` passed; no `dist/compare.html` diff was produced because the metric module is not imported by the UI bundle yet.

Feature flags live:

- `features.apexAnnotations`: default `false`, not wired to UI behavior.
- `features.apexMetrics`: default `false`, not wired to UI behavior.

Deferred to Phase 04.2:

- Add apex-side wheel surface/terrain selection.
- Keep distance/timing metrics unchanged while filling `surface_type` and `terrain_name` where wheel channels exist.
