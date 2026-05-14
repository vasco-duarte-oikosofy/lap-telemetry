# Phase 03 — Apex annotation files and validator

> **Development convention:** WE DEVELOP ON `main`. Write commits directly to `main`.

**Your task:** Implement Phase 3 from `specs/TRACK_OUTLINE_APEX_DISTANCE.md`.

**What to do:**
1. Read `AGENTS.md` and `TESTING_LESSONS.md`.
2. Read `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially "Phase 3 — Apex annotation files and validator" and the apex annotation contract in §0.2.
3. Read prior handoffs:
   - `phases_track_outline/00-schema-compatibility/handoff.md`
   - `phases_track_outline/01-recorder-track-edge-channels/handoff.md`
   - `phases_track_outline/02-loader-new-channels/handoff.md`
4. Write failing validator/loader tests first.
5. Implement the smallest annotation validator and loader needed for this phase.
6. Keep apex annotations data-only; do not wire them into the compare UI yet.

**Key requirements:**
- One JSON file per track layout follows this shape:
  ```json
  {
    "track_id": "circuit-de-spa-francorchamps",
    "layout_id": "default",
    "corners": [
      {
        "id": "t1",
        "name": "La Source",
        "s_start_m": 200,
        "s_end_m": 360,
        "apex_s_m": 285,
        "apex_side": "right"
      }
    ]
  }
  ```
- Validate required fields, numeric ordering, unique corner IDs, and `apex_side` values.
- Missing annotation files must return a clear "not configured" result without throwing in production code.
- Use feature flag `features.apexAnnotations` if this phase needs a delivery switch.
- Do not add apex metrics, apex tables, chart traces, map markers, editor UI, or sidecar export.

**Acceptance criteria:**
- Valid one-corner annotation loads successfully.
- Invalid `s_start_m >= apex_s_m` fails with a useful message.
- Invalid `apex_s_m >= s_end_m` fails with a useful message.
- Duplicate corner IDs fail with a useful message.
- Bad `apex_side` fails with a useful message.
- Missing annotation file returns “not configured” without throwing in production code.
- Existing test suite remains green.

**Suggested files to inspect first:**
- `web/js/appState.js` — current feature flag pattern.
- `web/js/trackOutlineChannels.js` — small pure-helper style from prior phases.
- `scripts/test_track_outline_schema_compat.js` — existing track-outline test pattern.
- `scripts/test_track_outline_loader_channels.js` — latest browser/session fixture pattern.

**When done:**
- `npm test` passes.
- `npm run build` succeeds and `dist/compare.html` is current if build output changes.
- `phases_track_outline/03-apex-annotations/learnings.md` exists.
- `phases_track_outline/03-apex-annotations/handoff.md` exists.
- Update `phases_track_outline/PLAN` to mark this phase DONE.
- Update `phases_track_outline/CURRENT` to `04-apex-metrics-one-corner`.
- Commit directly on `main`.

**Stop at green.** Do not start Phase 4.
