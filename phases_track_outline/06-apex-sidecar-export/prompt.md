# Phase 06 — Optional apex metrics sidecar export

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 6 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially:
   - §0.2 Apex annotation contract
   - §0.3 Apex metric contract
   - §0.5 Feature flags / delivery switches
   - "Phase 6 — Optional apex metrics sidecar export"
3. Read prior handoffs:
   - `phases_track_outline/03-apex-annotations/handoff.md`
   - `phases_track_outline/04-apex-metrics-one-corner/handoff.md`
   - `phases_track_outline/04.1-apex-metrics-all-corners/handoff.md`
   - `phases_track_outline/04.2-apex-surface-terrain/handoff.md`
   - `phases_track_outline/05-apex-metrics-ui/handoff.md`
4. Write failing tests first.
5. Implement the smallest optional CLI/helper that reads a session + apex annotation file and writes apex metrics JSON sidecar on demand.
6. Stop when the Phase 06 acceptance criteria pass; do not start drawer UI, map markers, annotation editing, or track outline/profile work.

**Current state:**

- `web/js/apexAnnotations.js`
  - Exports `validateApexAnnotations(input)`.
  - Exports `loadApexAnnotationsFile(filePath)` for Node/test/CLI-style consumers.
  - Loader returns `ok`, `invalid`, or `not_configured` status objects.
- `web/js/apexMetrics.js`
  - Exports `computeApexMetricForLap(data, corner, opts = {})`.
  - Exports `computeApexMetricsForSession(entry, annotationInput)`.
  - Aggregator accepts either loader-style `{ status: 'ok', annotations }` or a validated annotations object directly.
  - Returns `{ status: 'ok', metrics, reason: null }`, `{ status: 'not_configured', metrics: [], reason: null }`, or `{ status: 'unavailable', metrics: [], reason }`.
  - Does **not** fall back from `raw_lap_distance_m` to `lap_distance_m`.
  - Fills `surface_type` and `terrain_name` from apex-side wheels when channels exist.
- `web/js/ui.js` / `web/js/apexMetricsUi.js`
  - Browser can load annotation JSON separately from ordinary session sidecars and render text-only metrics behind `features.apexMetricsUi`.
  - This phase should not depend on the browser UI.
- `web/js/appState.js`
  - Has `features.apexAnnotations`, `features.apexMetrics`, and `features.apexMetricsUi`, all default `false`.
- Example real annotation created during Phase 05 follow-up:
  - `sessions/session_20260514T182139Z_circuit-de-spa-francorchamps-endurance_lmu.apex-annotations.json`
  - Treat it as a useful manual fixture/reference if present, but keep Phase 06 tests synthetic and deterministic.

**Implementation guidance:**

- Keep this phase optional and command/helper driven. Do not automatically write metrics during recording or browser loading.
- Prefer a small Node script or module over UI work. A command shape like this is acceptable if it fits existing project conventions:
  - `node scripts/export_apex_metrics.js --session <session.parquet> --annotations <apex.json> --out <metrics.json>`
- Reuse `loadApexAnnotationsFile()` and `computeApexMetricsForSession()`; do not duplicate metric math.
- Reuse or extract the smallest Parquet session-loading code needed for Node tests. Keep browser loader behavior unchanged.
- Define a minimal sidecar JSON shape around the §0.3 metric contract. Include enough metadata to identify inputs, for example:
  - `schema_version`
  - `source_session`
  - `annotation_track_id`
  - `annotation_layout_id`
  - `status`
  - `reason`
  - `metrics`
- Refuse to overwrite an existing output file unless an explicit overwrite option is passed.
- Legacy sessions should produce a valid JSON result with `status: "unavailable"`, empty `metrics`, and a clear `reason`; they should not crash.
- If annotations are missing/invalid, return a useful non-zero CLI error for invalid input. Missing annotation file may follow the existing `not_configured` status only if the command deliberately supports it; keep behavior documented and tested.

**Acceptance criteria:**

- CLI/helper test: fixture session + fixture annotations produce expected JSON metrics matching the §0.3 contract.
- CLI/helper test: existing output file is not overwritten by default.
- CLI/helper test: explicit overwrite option replaces an existing output file.
- CLI/helper test: legacy session produces JSON with `status: "unavailable"`, null/empty metrics as appropriate, and a clear reason.
- Existing compare UI and Phase 05 apex metrics UI remain unchanged.
- Existing `npm test` remains green.

**Suggested tests:**

- Add a new Node test such as `scripts/test_apex_metrics_export.js` and include it in `npm test`.
- Build small synthetic Parquet fixtures inside the test, following the pattern in `scripts/test_track_outline_loader_channels.js` or other track-outline tests.
- Include one configured fixture with two laps and at least two corners so output ordering is proved.
- Include one legacy fixture without `raw_lap_distance_m` / edge channels for unavailable output.
- Include overwrite protection assertions by writing a sentinel output file before invoking the command.
- Assert exact JSON fields and deterministic numeric values. Avoid relying on the large real `sessions/` files for acceptance.

**Suggested files to inspect first:**

- `web/js/apexMetrics.js` — current pure metric + session aggregator.
- `web/js/apexAnnotations.js` — validator and Node annotation loader.
- `scripts/test_apex_metrics_aggregate.js` — aggregator expectations and ordering.
- `scripts/test_apex_metrics_surface_terrain.js` — surface/terrain expectations.
- `scripts/test_track_outline_loader_channels.js` — synthetic Parquet creation pattern.
- `web/js/ui.js` and `web/js/pipeline.js` — browser session-loading shapes if you need to mirror `entry.data` / `segments` in Node.
- `package.json` — add the new Phase 06 test to `npm test`.

**Out of scope:**

- Browser UI export buttons.
- Automatic export during recording or browser loading.
- Map apex markers or labels.
- Closeable drawer UI for apex metrics.
- Annotation editor UI.
- Track-width/profile/outline work.
- Official track data import.
- Any fallback from `lap_distance_m` to `raw_lap_distance_m`.

**When done:**

- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current. If no frontend bundle changes occur, still run the build and document whether `dist/compare.html` changed.
- `phases_track_outline/06-apex-sidecar-export/learnings.md` exists.
- `phases_track_outline/06-apex-sidecar-export/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `07-width-profile-cli`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 07.
