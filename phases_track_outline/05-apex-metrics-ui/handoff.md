# Handoff — Phase 05 Apex Metrics UI

State on disk:

- `web/js/appState.js`
  - Added `features.apexMetricsUi`, default `false`.
  - Added `apexAnnotationsByLayout` for validated browser-loaded annotation JSON.
- `web/js/ui.js`
  - `.json` files matching the apex annotation contract are validated with `validateApexAnnotations()` and stored separately from session sidecars.
  - Ordinary session sidecar JSON loading is unchanged.
- `web/js/apexMetricsUi.js`
  - New text-only renderer for `#apex-metrics-panel`.
  - Matches loaded session metadata (`sidecar.track`/`track_id`, layout fields, default layout `default`) to stored annotations.
  - Uses `computeApexMetricsForSession()` for the currently selected session lap only.
  - Renders corner, lap, apex distance, timing as `late`/`early`/`exact`, surface, and terrain.
  - Empty states:
    - `No apex annotations for this track/layout`
    - `Record a new session to capture track-edge channels`
- `web/compare.html`
  - Added hidden `#apex-metrics-panel`; default rendering remains unchanged while the feature flag is off.
- `web/js/apexAnnotations.js`
  - Node-only file loader now uses an indirect dynamic import so the validator module can be bundled for browser use.
- `scripts/test_apex_metrics_ui.js`
  - New Playwright render coverage for configured rows, late/early labels, unconfigured annotation state, and legacy missing-channel state while the rest of compare UI remains usable.
- `package.json`
  - `npm test` now includes the Phase 05 UI test.
- `dist/compare.html`
  - Rebuilt with the Phase 05 bundle.
- `phases_track_outline/PLAN`
  - Marks Phase 05 DONE.
- `phases_track_outline/CURRENT`
  - Set to `06-apex-sidecar-export`.

Feature flags live:

- `features.apexMetricsUi`: default `false`; enable from the feature flag dropdown or `window.__setFeatureFlag('apexMetricsUi', true)` after loading an annotation JSON and session sidecar.

Deferred to Phase 06:

- Persist/export apex metrics sidecars. No export path was added in this phase.
- Map markers, chart traces, annotation editing, and outline/profile work remain out of scope.

Verification:

- `npm test` passed.
- `npm run build` passed.
