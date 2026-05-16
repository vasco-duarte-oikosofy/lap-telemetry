# Phase 05 — Apex metrics UI, text-only

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 5 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially:
   - §0.2 Apex annotation contract
   - §0.3 Apex metric contract
   - §0.5 Feature flags / delivery switches
   - "Phase 5 — Apex metrics UI, text-only"
3. Read prior handoffs:
   - `phases_track_outline/02-loader-new-channels/handoff.md`
   - `phases_track_outline/03-apex-annotations/handoff.md`
   - `phases_track_outline/04-apex-metrics-one-corner/handoff.md`
   - `phases_track_outline/04.1-apex-metrics-all-corners/handoff.md`
   - `phases_track_outline/04.2-apex-surface-terrain/handoff.md`
4. Write failing browser/render tests first.
5. Implement the smallest text-only UI around the existing apex annotation + metric helpers.
6. Stop when the Phase 05 acceptance criteria pass; do not start map markers, sidecar export, or outline/profile work.

**Current state:**

- `web/js/apexAnnotations.js`
  - Exports `validateApexAnnotations(input)`.
  - Exports `loadApexAnnotationsFile(filePath)` for Node/test/CLI-style consumers only.
  - Browser UI does **not** yet have an annotation discovery/loading mechanism.
- `web/js/apexMetrics.js`
  - Exports `computeApexMetricForLap(data, corner, opts = {})`.
  - Exports `computeApexMetricsForSession(entry, annotationInput)`.
  - Aggregator accepts either loader-style `{ status: 'ok', annotations }` or a validated annotations object directly.
  - Returns `{ status: 'ok', metrics, reason: null }`, `{ status: 'not_configured', metrics: [], reason: null }`, or `{ status: 'unavailable', metrics: [], reason }`.
  - Does **not** fall back from `raw_lap_distance_m` to `lap_distance_m`.
  - Fills `surface_type` and `terrain_name` from apex-side wheels when channels exist.
- `web/js/ui.js`
  - Loads `.json` files today as generic session sidecars via `loadSidecar()`.
  - Loads Parquet telemetry with all `TRACK_OUTLINE_CHANNELS` into each `store` entry.
- `web/js/appState.js`
  - Has `features.apexAnnotations` and `features.apexMetrics`, both default `false`.
  - Does **not** yet have `features.apexMetricsUi`; add it for this phase, default `false`.
- `web/compare.html`
  - Has loader, pickers, legend, circuit map, and `#plots-container` / `#plot-area`.
  - No apex metrics container exists yet.

**Implementation guidance:**

- Keep this phase text-only. A small panel/table near the existing compare output is enough.
- Gate the UI behind `features.apexMetricsUi` so default rendering remains unchanged until the flag is enabled.
- Use the existing `computeApexMetricsForSession()` aggregator; do not duplicate metric math in UI code.
- Use validated annotation objects. Add the smallest browser-side way for tests/users to provide annotations.
  - Prefer reusing `.json` file loading if simple, but do not break existing sidecar metadata loading.
  - It is acceptable to recognize apex annotation JSON by its shape (`track_id`, `layout_id`, `corners`) and store it separately from session sidecars.
  - If you add test/debug hooks for annotation setup, keep production behavior safe and documented in the handoff.
- Match annotations to the loaded session using the smallest available metadata source.
  - Session JSON sidecars commonly include track identity; inspect current sidecar shape before choosing fields.
  - If no matching annotation is configured, show the required no-annotation empty state.
- Render metrics for the currently selected **session lap**. The reference lap can remain out of scope unless needed by existing render flow.
- Display at minimum:
  - corner name
  - lap label
  - apex distance
  - timing labeled `early` / `late` / exact where appropriate
  - surface type when non-null
  - terrain name when non-null
- Formatting should be simple and deterministic for tests:
  - meters with a fixed precision or clear integer formatting
  - `late` for positive timing error
  - `early` for negative timing error
  - `—` or similar for missing surface/terrain

**Acceptance criteria:**

- Render test: configured fixture displays expected corner rows and formatted values.
- Render test: late values are labeled `late`; early values are labeled `early`.
- Render test: unconfigured track shows `No apex annotations for this track/layout`.
- Render test: legacy fixture shows `Record a new session to capture track-edge channels`.
- Existing compare UI still works for legacy sessions.
- Existing `npm test` remains green.

**Suggested tests:**

- Add a new Playwright test such as `scripts/test_apex_metrics_ui.js` and include it in `npm test`.
- Build small synthetic Parquet fixtures inside the test, following the pattern in `scripts/test_track_outline_loader_channels.js`.
- Include one configured fixture with two corners where one timing error is late and one is early.
- Include surface/terrain channels in the configured fixture so Phase 04.2 output appears in the UI.
- Include a legacy fixture without `raw_lap_distance_m` / edge channels for the missing-channel empty state.
- Follow `TESTING_LESSONS.md`: use debug hooks for state, wait for data state, and re-query DOM after render.

**Suggested files to inspect first:**

- `web/js/apexMetrics.js` — current pure metric + session aggregator.
- `web/js/apexAnnotations.js` — validator and annotation status style.
- `web/js/trackOutlineChannels.js` — optional telemetry channel list.
- `web/js/ui.js` — file loading and JSON sidecar behavior.
- `web/js/main.js` — `renderAll()` and compare render flow.
- `web/js/appState.js` — feature flag pattern.
- `web/compare.html` and `web/css/styles.css` — existing panel/container conventions.
- `web/js/debugHooks.js` — test hooks for Playwright.
- `scripts/test_track_outline_loader_channels.js` — synthetic Parquet + browser-load pattern.
- `scripts/test_apex_metrics_aggregate.js` and `scripts/test_apex_metrics_surface_terrain.js` — metric expectations.

**Out of scope:**

- Map apex markers or labels.
- Charts/traces for apex metrics.
- Annotation editor UI.
- Apex metrics sidecar export.
- Track-width/profile/outline work.
- Official track data import.
- Any fallback from `lap_distance_m` to `raw_lap_distance_m`.

**When done:**

- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current.
- `phases_track_outline/05-apex-metrics-ui/learnings.md` exists.
- `phases_track_outline/05-apex-metrics-ui/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `06-apex-sidecar-export`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 06.
