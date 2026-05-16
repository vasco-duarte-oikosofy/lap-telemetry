# Phase 00 — Quick and dirty TUMFTM alignment try

> **Development convention:** work on `main`. This phase is a spike/proof, but still keep changes reviewable and committed directly to `main` when complete.

## Goal

Determine quickly whether manually aligned TUMFTM track geometry can produce a Spa track outline that is visibly better than the current learned-boundary output.

This phase answers one question only:

> Can a simple global manual transform align TUMFTM Spa outline geometry to our simulator trajectory coordinates well enough that Bus Stop and La Source look clearly better than the learned outline?

## Required reading

1. `AGENTS.md`
2. `TESTING_LESSONS.md`
3. `specs/TUMFTM_BASED_TRACK_MAP_OUTLINE_GENERATION_BY_HAND.md`
4. `specs/TRACK_OUTLINE_APEX_DISTANCE.md`, especially the Phase 9.2/9.3 deferred visual-QA notes
5. Prior handoffs/learnings:
   - `phases_track_outline/09.2-boundary-smoothing/handoff.md`
   - `phases_track_outline/09.2-boundary-smoothing/learnings.md`
   - `phases_track_outline/09.3-infer-missing-boundary-widths/handoff.md`
   - `phases_track_outline/09.3-infer-missing-boundary-widths/learnings.md`

## Scope

Build a standalone local/offline alignment prototype. Keep it simple.

Suggested artifacts:

- `tools/manual_outline_align.html` — standalone canvas tool loaded via `file://`
- optional helper script(s) under `scripts/` to prepare input JSON:
  - export one or more Spa simulator trajectories/path points to a simple JSON shape
  - convert TUMFTM CSV to a simple JSON shape if needed
- optional generated spike artifacts under a clearly named local data folder

Do **not** integrate this into the compare UI yet.
Do **not** build manifest/alias lookup.
Do **not** build a polished editor.
Do **not** add piecewise warping or optimization unless the simple approach cannot even be evaluated.

## Tool behavior

The HTML tool should load local files via file inputs:

1. Simulator trajectory/reference JSON
2. TUMFTM track JSON or CSV-derived JSON
3. Optional extra simulator trajectories JSON

The canvas should draw:

- reference simulator trajectory in a bright color
- optional extra simulator trajectories in faint colors
- transformed TUMFTM centerline
- transformed TUMFTM left/right boundaries

Manual controls should be minimal but usable:

- scale
- rotation
- translate x
- translate y
- flip x
- flip y
- reverse point order

Keyboard shortcuts are encouraged if quick:

- arrow keys: translate
- shift+arrows: larger translate
- `q` / `e`: rotate
- `+` / `-`: scale
- `f`: flip one axis or cycle flips
- `r`: reverse point order

Add an `Export aligned outline JSON` button that writes/copies/downloads transformed geometry plus alignment parameters.

## Simple input shape

Use or produce a simple trajectory JSON shape like:

```json
{
  "track_name": "Spa-Francorchamps",
  "trajectories": [
    {
      "name": "reference lap",
      "points": [
        { "x": 123.4, "y": -55.2 }
      ]
    }
  ]
}
```

Use `x = simulator/world x`, `y = simulator/world z` if the source data uses `x_m`/`z_m`.

Use or produce a simple TUMFTM JSON shape like:

```json
{
  "track_name": "Spa TUMFTM",
  "points": [
    {
      "x": 10.2,
      "y": 44.1,
      "w_left": 7.5,
      "w_right": 8.0
    }
  ]
}
```

The tool may derive boundaries in-browser from centerline + widths.

## Export shape

The exported aligned outline can be rough but should include:

```json
{
  "schema_version": 0,
  "source": "TUMFTM manual alignment spike",
  "track_name": "Spa-Francorchamps",
  "alignment": {
    "scale": 1.0,
    "rotation_rad": 0.0,
    "translate_x": 0.0,
    "translate_y": 0.0,
    "flip_x": false,
    "flip_y": false,
    "reverse_point_order": false
  },
  "centerline": [{ "x": 1, "y": 2 }],
  "left_boundary": [{ "x": 0, "y": 2 }],
  "right_boundary": [{ "x": 2, "y": 2 }]
}
```

Schema version `0` is fine because this is a spike artifact.

## Success criteria

This phase succeeds only if visual QA shows a clear win over the current learned-boundary output.

A success means:

- Bus Stop reads as a continuous believable track corridor.
- La Source is smooth and plausible, not jagged/noisy.
- Major Spa landmarks line up with the simulator trajectory:
  - start/finish straight
  - Eau Rouge/Raidillon
  - Les Combes
  - Bus Stop
- Extra real trajectories, if loaded, sit inside or near the TUMFTM outline for most of the lap.
- The alignment can be reached with a simple global transform in a reasonable amount of manual time.
- The exported JSON can be reloaded into the tool and produces the same visual alignment.

This phase fails if:

- A single global transform cannot align both Bus Stop and La Source acceptably.
- The outline remains obviously worse than or not meaningfully better than the previous best learned-boundary output.
- Manual alignment is too fragile or confusing to repeat.
- TUMFTM data/layout appears incompatible with the simulator layout.

## Testing expectation

Because this is a visual spike, do not overbuild automated tests.

Minimum checks:

- Any helper script has a small smoke test or at least a deterministic CLI run documented in handoff.
- The HTML tool loads sample/minimal input without throwing.
- Exported JSON parses and contains centerline/left/right arrays.
- Run `npm test` before committing unless explicitly documented why not.
- Run `npm run build` if any frontend/build-relevant files changed. A standalone `tools/*.html` file normally should not affect `dist/compare.html`, but follow project rules if unsure.

## Visual QA instructions

1. Load one clean Spa simulator trajectory as the reference.
2. Load TUMFTM Spa geometry.
3. Manually align with scale/rotation/translation/flips/reverse as needed.
4. Load optional extra Spa trajectories.
5. Compare visually against:
   - current learned-boundary Spa output
   - 9.3 inferred Spa output
   - user's previous best Bus Stop screenshot if available
6. Document the result honestly.

## Required end artifacts

- `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/learnings.md`
- `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/handoff.md`
- Update `phases_TUMFTM_based_track_map_outline/PLAN` status for Phase 00.
- Commit on `main`.

## Stop condition

Stop after the visual assessment. Do not start production static-outline rendering or manifest work in this phase.
