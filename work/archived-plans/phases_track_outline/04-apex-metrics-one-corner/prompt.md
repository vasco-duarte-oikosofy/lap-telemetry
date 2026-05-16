# Phase 04 — Apex metrics for one lap, one configured corner

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 4 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially:
   - §0.1 Raw recorder channels
   - §0.2 Apex annotation contract
   - §0.3 Apex metric contract
   - "Phase 4 — Apex metrics for one lap, one configured corner"
3. Read prior handoffs:
   - `phases_track_outline/00-schema-compatibility/handoff.md`
   - `phases_track_outline/01-recorder-track-edge-channels/handoff.md`
   - `phases_track_outline/02-loader-new-channels/handoff.md`
   - `phases_track_outline/03-apex-annotations/handoff.md`
4. Write failing metric tests first.
5. Implement the smallest pure metric function for one lap and one corner.
6. Keep output in memory/data only; do not wire into the compare UI yet.

**Key requirements:**
- Input should be compatible with the current loaded session shape from Phase 02 and the validated annotation corner from Phase 03.
- Select samples whose `raw_lap_distance_m` is between `corner.s_start_m` and `corner.s_end_m`, inclusive.
- Find the selected sample closest to `corner.apex_s_m`.
- Return an `ApexMetric` shaped like:
  ```ts
  type ApexMetric = {
    corner_id: string;
    corner_name: string;
    lap: number | string;
    apex_distance_m: number | null;
    apex_timing_error_m: number | null;
    surface_type: string | null;
    terrain_name: string | null;
    sample_s_m: number | null;
  };
  ```
- For this phase, surface/terrain may remain `null`; Phase 4.2 handles wheel-side surface/terrain.
- Compute `apex_timing_error_m = sample_s_m - corner.apex_s_m`; positive means late, negative means early.
- Inside-edge distance should use `distance_to_track_edge_m` when available. If needed, derive from `track_edge_m - abs(path_lateral_m)` only when both fields exist at the selected sample.
- Missing required channels (`raw_lap_distance_m`, and either `distance_to_track_edge_m` or both `path_lateral_m` + `track_edge_m`) must return null metric fields instead of throwing.
- Do **not** silently use `lap_distance_m` as `raw_lap_distance_m`.
- Use feature flag `features.apexMetrics` if this phase needs a delivery switch.

**Acceptance criteria:**
- Metric test: closest sample to `apex_s_m` is selected correctly.
- Metric test: `apex_timing_error_m` is positive for late and negative for early fixtures.
- Metric test: inside-edge distance uses the correct selected sample and expected numeric value.
- Missing `raw_lap_distance_m`, `path_lateral_m`, or `track_edge_m` / `distance_to_track_edge_m` returns nulls instead of throwing.
- Existing test suite remains green.

**Suggested files to inspect first:**
- `web/js/apexAnnotations.js` — Phase 03 validator/loader style.
- `web/js/trackOutlineChannels.js` — raw-distance helper and optional channel handling.
- `scripts/test_apex_annotations.js` — latest pure test pattern.
- `scripts/test_track_outline_loader_channels.js` — loaded session data shape expectations.
- `web/js/appState.js` — feature flag pattern.

**Out of scope:**
- Multiple corners or multiple laps aggregation.
- Surface/terrain wheel-side selection.
- Apex metrics UI/table.
- Map markers or chart traces.
- Sidecar export.
- Annotation editor UI.
- Any user-visible UI change.

**When done:**
- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current if build output changes.
- `phases_track_outline/04-apex-metrics-one-corner/learnings.md` exists.
- `phases_track_outline/04-apex-metrics-one-corner/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `04.1-apex-metrics-all-corners`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 4.1.
