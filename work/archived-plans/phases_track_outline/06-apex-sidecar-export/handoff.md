# Handoff — Phase 06 Apex Sidecar Export

State on disk:

- `scripts/export_apex_metrics.js`
  - New optional Node CLI/helper.
  - CLI shape: `node scripts/export_apex_metrics.js --session <session.parquet> --annotations <apex.json> --out <metrics.json> [--overwrite]`.
  - Exports `exportApexMetricsSidecar({ sessionPath, annotationsPath, outPath, overwrite })` for tests/automation.
  - Reuses `loadApexAnnotationsFile()`, `computeApexMetricsForSession()`, and `buildSegments()`.
  - Writes deterministic JSON with `schema_version`, source paths, annotation track/layout IDs, `status`, `reason`, and §0.3 `metrics`.
  - Refuses to overwrite existing output unless `overwrite: true` / `--overwrite` is passed.
  - Invalid or missing annotation files fail non-zero in CLI use; legacy telemetry writes `status: "unavailable"` with empty metrics.
- `scripts/test_apex_metrics_export.js`
  - Builds synthetic Parquet fixtures with Python/pyarrow.
  - Covers configured two-lap/two-corner export, CLI invocation, invalid annotation CLI failure, overwrite refusal, explicit overwrite, and legacy unavailable output.
- `package.json`
  - Adds the Phase 06 export test to `npm test`.
- `phases_track_outline/PLAN`
  - Marks `06-apex-sidecar-export` DONE.
- `phases_track_outline/CURRENT`
  - Set to `07-width-profile-cli`.
- `dist/compare.html`
  - Rebuilt with `npm run build`; no frontend source changed in this phase.

Feature flags live:

- No new feature flags. The exporter is optional and command-driven only.
- Existing `features.apexAnnotations`, `features.apexMetrics`, and `features.apexMetricsUi` remain unchanged.

Verification:

- `npm test` passed.
- `npm run build` passed.

Deferred:

- No automatic sidecar generation during recording or browser loading.
- Width/profile CLI starts in Phase 07.
- Drawer UI, map markers, annotation editing, and track outline/profile rendering remain out of scope.
