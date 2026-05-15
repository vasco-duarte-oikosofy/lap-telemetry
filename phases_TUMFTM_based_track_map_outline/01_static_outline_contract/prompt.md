# Phase 01 — Static outline contract

> **Development convention:** work on `main`. This phase is a production/static-data contract phase, not runtime rendering.

## Mandatory pre-implementation user review gate

Before making any code or data changes, STOP and ask the user to review the intended Phase 01 artifact plan.

Present the user with:

1. Proposed production JSON path:
   - `data/track-outlines/spa-francorchamps.json`
2. Proposed schema version:
   - `schema_version: 1`
3. Proposed source input:
   - accepted Phase 00 aligned export, or a user-provided equivalent accepted JSON
4. Proposed top-level metadata fields:
   - `schema_version`
   - `source`
   - `track_name`
   - `sim_track_name`
   - `layout_name`
   - `coordinate_system`
   - `units`
   - `alignment`
   - `visual_qa`
   - `centerline`
   - `left_boundary`
   - `right_boundary`
5. Explicit caveat to include in metadata/docs:
   - TUMFTM widths are satellite/image-derived approximations, not official FIA geometry and not authoritative simulator track limits.
6. Confirm no runtime compare-UI integration will be implemented in this phase.

Wait for explicit user approval before implementation. If the user changes the desired schema/path/metadata, update the Phase 01 plan accordingly before coding.

## Goal

Promote the accepted Spa/TUMFTM manual-alignment spike output into a reviewed production static outline JSON contract.

This phase answers one question only:

> Do we have a clear, validated, versioned static-outline artifact shape for Spa in simulator coordinates, ready for a later runtime-rendering phase?

## Required reading

1. `AGENTS.md`
2. `TESTING_LESSONS.md`
3. `specs/TUMFTM_BASED_TRACK_MAP_OUTLINE_GENERATION_BY_HAND.md`
4. `phases_TUMFTM_based_track_map_outline/PLAN`
5. `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/handoff.md`
6. `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/learnings.md`
7. Phase 00 artifacts, especially:
   - `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/artifacts/aligned-outline-spike.json`
   - `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/artifacts/alignment-overview.png`

## Scope

Create the static outline contract and one Spa artifact only.

Suggested artifact:

- `data/track-outlines/spa-francorchamps.json`

Suggested helper/test artifacts, only if needed:

- a small validator module or script for static outline JSON
- a small test script that validates the Spa artifact shape

Do **not** integrate this into the compare UI yet.
Do **not** add manifest or alias lookup.
Do **not** add runtime TUMFTM CSV parsing.
Do **not** add width scaling unless the user explicitly approves it during the pre-implementation review.
Do **not** polish the Phase 00 alignment tool.

## Production JSON shape

Use schema version `1` for the production static artifact.

Suggested shape:

```json
{
  "schema_version": 1,
  "source": "TUMFTM manual alignment",
  "track_name": "Circuit de Spa-Francorchamps",
  "sim_track_name": "Spa-Francorchamps",
  "layout_name": "default",
  "coordinate_system": "sim_xy",
  "units": "sim_units",
  "alignment": {
    "method": "manual_similarity_transform",
    "scale": 1,
    "rotation_rad": 0.0004,
    "translate_x": -165,
    "translate_y": 632,
    "flip_x": false,
    "flip_y": false,
    "reverse_point_order": false,
    "source_phase": "phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try",
    "notes": "Aligned manually against LMU Spa trajectory. Bus Stop, La Source, Eau Rouge/Raidillon, Les Combes checked visually."
  },
  "visual_qa": {
    "status": "accepted",
    "notes": "Phase 00 user review: alignment looked good and proved the approach."
  },
  "caveats": [
    "TUMFTM widths are satellite/image-derived approximations, not official FIA geometry.",
    "This outline is visual context only and is not an authoritative simulator track-limits source."
  ],
  "centerline": [{ "x": 1, "y": 2 }],
  "left_boundary": [{ "x": 0, "y": 2 }],
  "right_boundary": [{ "x": 2, "y": 2 }]
}
```

The actual coordinate arrays should come from the user-reviewed accepted Phase 00 export.

## Testing expectation

Keep tests small. This is a data contract phase.

Minimum checks:

- The Spa static outline JSON parses.
- `schema_version === 1`.
- Required metadata fields are present.
- `centerline`, `left_boundary`, and `right_boundary` are non-empty arrays of finite `{ x, y }` points.
- Boundary arrays have the same length as centerline unless the user explicitly approves a different contract.
- Caveat text makes clear that TUMFTM widths are approximate/non-official.
- Existing tests remain green if run; for this data-only phase, at least run the new contract test and document if the full suite is skipped as too expensive for the handoff.

## Acceptance criteria

- User approved the intended schema/path/metadata before implementation.
- `data/track-outlines/spa-francorchamps.json` exists and is reviewed static data, not a spike schema dump.
- The artifact uses `schema_version: 1`.
- The artifact preserves transformed simulator-coordinate centerline/left/right arrays.
- Metadata includes source, alignment parameters, coordinate-system notes, and visual QA notes.
- Caveats explicitly state that TUMFTM widths are approximate and non-official.
- No compare-UI/runtime behavior changes were made.
- A deterministic validation/test command exists and passes.

## Required end artifacts

- `phases_TUMFTM_based_track_map_outline/01_static_outline_contract/learnings.md`
- `phases_TUMFTM_based_track_map_outline/01_static_outline_contract/handoff.md`
- Update `phases_TUMFTM_based_track_map_outline/PLAN` status for Phase 01.
- Commit on `main`.

## Stop condition

Stop after the static Spa artifact contract is validated and committed. Do not start runtime rendering, manifest lookup, aliases, or further alignment tooling in this phase.
