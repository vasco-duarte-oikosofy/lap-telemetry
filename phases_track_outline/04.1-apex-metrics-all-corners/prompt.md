# Phase 04.1 — Apex metrics for all laps and configured corners

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 4.1 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially:
   - §0.2 Apex annotation contract
   - §0.3 Apex metric contract
   - "Phase 4 — Apex metrics for one lap, one configured corner"
   - "Phase 4.1 — Apex metrics for all laps and corners"
3. Read prior handoffs:
   - `phases_track_outline/02-loader-new-channels/handoff.md`
   - `phases_track_outline/03-apex-annotations/handoff.md`
   - `phases_track_outline/04-apex-metrics-one-corner/handoff.md`
4. Write failing aggregator tests first.
5. Implement the smallest aggregator around the Phase 04 pure helper.
6. Keep output in memory/data only; do not wire into the compare UI yet.

**Current Phase 04 helper:**

- `web/js/apexMetrics.js` exports `computeApexMetricForLap(data, corner, opts = {})`.
- It accepts one loaded lap/session-shaped `data` object and one validated corner.
- It returns one `ApexMetric` with null computed fields when telemetry is unavailable.
- It does **not** fall back from `raw_lap_distance_m` to `lap_distance_m`.
- `features.apexMetrics` exists in `web/js/appState.js`, default `false`.

**Key requirements:**

- Input should be compatible with:
  - loaded session data from Phase 02
  - validated annotations from Phase 03
  - Phase 04 metric helper output
- Compute apex metrics for every configured corner on every loaded lap.
- Preserve stable ordering:
  1. lap order
  2. annotation file corner order
- Return one metric per `(lap, corner)` pair.
- Define clear data-only empty/unavailable states for:
  - no annotation file / not configured
  - no compatible telemetry
- Do **not** render any UI, table, marker, trace, or chart.
- Do **not** implement surface/terrain wheel-side selection; Phase 4.2 owns that.
- Do **not** silently use `lap_distance_m` as `raw_lap_distance_m`.

**Acceptance criteria:**

- Aggregator test: returns one metric per `(lap, corner)` pair.
- Aggregator test: output ordering is stable and matches fixture lap order, then annotation corner order.
- Empty-state test: no annotation file returns an empty result with a `not_configured` status.
- Unavailable telemetry test: legacy telemetry returns an empty/unavailable result without breaking existing compare behavior.
- Existing test suite remains green.

**Suggested files to inspect first:**

- `web/js/apexMetrics.js` — Phase 04 one-lap/one-corner helper.
- `web/js/apexAnnotations.js` — validator/loader status style.
- `web/js/trackOutlineChannels.js` — optional channel and raw-distance helpers.
- `scripts/test_apex_metrics.js` — latest pure metric test pattern.
- `scripts/test_track_outline_loader_channels.js` — loaded session data shape expectations.
- `web/js/appState.js` — feature flag pattern.

**Out of scope:**

- Surface/terrain wheel-side selection.
- Apex metrics UI/table.
- Map markers or chart traces.
- Sidecar export.
- Annotation editor UI.
- Any user-visible UI change.

**When done:**

- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current if build output changes.
- `phases_track_outline/04.1-apex-metrics-all-corners/learnings.md` exists.
- `phases_track_outline/04.1-apex-metrics-all-corners/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `04.2-apex-surface-terrain`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 4.2.
