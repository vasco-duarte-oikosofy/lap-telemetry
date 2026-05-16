# Phase 02 — Runtime static outline rendering

> **Development convention:** work on `main`. This phase is a runtime rendering phase for one explicit static outline artifact only.

## Goal

Load the production Spa static outline artifact and render it behind existing lap trajectories in the compare UI.

This phase answers one question only:

> Can the compare page display the accepted static Spa outline as visual context, without adding track discovery, aliases, an editor, or runtime TUMFTM conversion?

## Required reading

1. `AGENTS.md`
2. `TESTING_LESSONS.md`
3. `ARCHITECTURE.md`
4. `RENDER_DESIGN.md`
5. `phases_TUMFTM_based_track_map_outline/PLAN`
6. `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/handoff.md`
7. `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/learnings.md`
8. `phases_TUMFTM_based_track_map_outline/01_static_outline_contract/handoff.md`
9. `phases_TUMFTM_based_track_map_outline/01_static_outline_contract/learnings.md`
10. Static artifact:
    - `data/track-outlines/spa-francorchamps.json`

Before writing a new test or fixing a failing test, read `TESTING_LESSONS.md`.

## Scope

Implement the smallest runtime path that renders one explicit static outline:

- Load `data/track-outlines/spa-francorchamps.json` as a bundled/static app asset.
- Parse/validate only what the renderer needs from schema v1.
- Draw `left_boundary`, `right_boundary`, and optionally `centerline` behind existing lap trajectories.
- Keep the outline visually subordinate to telemetry traces.
- Keep the rendering compatible with the existing map viewport/zoom/pan behavior.

Do **not** add manifest or alias lookup.
Do **not** add fuzzy track matching.
Do **not** add automatic track/layout selection.
Do **not** parse TUMFTM CSV at runtime.
Do **not** perform alignment, width derivation, or width scaling at runtime.
Do **not** add or polish an editor.
Do **not** change the static artifact schema unless a failing test reveals a real contract issue.

## Suggested implementation approach

Stay test-first and focused:

1. Add a small failing test that proves a static outline can be loaded and rendered in the compare UI/map layer.
2. Find the existing map rendering code and data-loading path.
3. Add the minimal loader/import for the one Spa artifact.
4. Add a small renderer path for static outline geometry behind trajectories.
5. Keep styling simple and deterministic enough for tests.

Prefer small helper modules only if they make the code clearer. Follow existing file architecture and read nearby files before adding a new one.

## Rendering expectations

- The outline should be drawn behind lap trajectories.
- The outline should not affect telemetry data, lap selection, metrics, or charts.
- The map should continue to frame/scale existing trajectory data correctly.
- If the existing map bounds are trajectory-derived, include the outline only if doing so does not create surprising zoom behavior. Prefer preserving current trajectory-focused framing unless the existing architecture naturally supports combined bounds.
- Use subdued styling for context, for example low-alpha boundaries and/or dashed centerline, consistent with existing canvas/SVG conventions.

## Testing expectation

Minimum checks:

- A deterministic test confirms the Spa static outline artifact is available to runtime code.
- A rendering/unit/integration test confirms outline geometry is sent to or drawn by the map layer behind trajectories.
- Existing static artifact contract test still passes.
- Existing compare/map behavior tests remain green.

Run and document:

- The new focused test command.
- `npm test`.
- `npm run build`.

## Acceptance criteria

- Compare UI renders the Spa static outline behind existing trajectories.
- Runtime uses the schema v1 artifact at `data/track-outlines/spa-francorchamps.json`.
- No manifest, aliases, fuzzy lookup, editor, runtime TUMFTM parsing, or runtime alignment math were added.
- Existing trajectory rendering behavior remains intact.
- Tests pass.
- `npm run build` succeeds and rewrites `dist/compare.html`.

## Required end artifacts

- `phases_TUMFTM_based_track_map_outline/02_runtime_static_outline_rendering/learnings.md`
- `phases_TUMFTM_based_track_map_outline/02_runtime_static_outline_rendering/handoff.md`
- Update `phases_TUMFTM_based_track_map_outline/PLAN` status for Phase 02.
- Update `phases_TUMFTM_based_track_map_outline/CURRENT` if the phase is completed or handed off.
- Commit on `main`.

## Stop condition

Stop after the one explicit Spa static outline renders in the compare UI and the phase is documented. Do not start offline workflow hardening, manifest work, aliases, fuzzy matching, or additional track outlines in this phase.
