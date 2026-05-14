# Handoff — Phase 03 Apex Annotations

State on disk:

- `web/js/apexAnnotations.js`
  - Added `validateApexAnnotations(input)`.
  - Validates required root fields, required corner fields, finite numeric distances, `s_start_m < apex_s_m < s_end_m`, unique corner IDs, and `apex_side` of `left` or `right`.
  - Returns `{ ok: true, annotations, errors: [] }` for valid data and `{ ok: false, errors }` for invalid data.
  - Added `loadApexAnnotationsFile(filePath)` for Node/test/CLI-style consumers.
  - Loader returns `{ status: 'ok', annotations, errors: [] }`, `{ status: 'invalid', annotations: null, errors }`, or `{ status: 'not_configured', annotations: null, errors: [] }` for missing files.
- `web/js/appState.js`
  - Added feature flag `features.apexAnnotations`, default `false`.
- `scripts/test_apex_annotations.js`
  - Covers valid one-corner annotation loading.
  - Covers invalid ordering on both sides of `apex_s_m`.
  - Covers duplicate IDs, bad `apex_side`, missing required root field, and missing file as `not_configured`.
- `npm test` includes the Phase 03 annotation test.
- `dist/compare.html` was rebuilt with `npm run build`.
- `phases_track_outline/PLAN` marks this phase DONE.
- `phases_track_outline/CURRENT` is `04-apex-metrics-one-corner`.

Feature flags live:

- `features.apexAnnotations`: present, default `false`, not wired to UI behavior yet.

Deferred to Phase 04:

- Compute one-lap/one-corner apex metrics from validated annotations and loaded telemetry channels.
- Keep missing telemetry channels returning null/unavailable metric fields rather than throwing.
