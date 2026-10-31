# Slice 02 — `turns` block in the outline schema (+ preservation guard)

Bake curated turn labels into the outline data so the renderer never invents
data (spec: `docs/specs/MAP_TURN_NAMES.md`).

1. Production bake tool `dev/scripts/bake_outline_turns.py` (from the slice-01
   spike): `apex_s_m` -> world `x, y`, `outward`/`tangent` unit vectors,
   `short_name` passthrough, unwrap-aware lap interpolation, deterministic
   model choice when a track has one model per car, `--all` and `--check`.
2. `turns` block written into the Silverstone International outline (the
   vertical target for this slice).
3. **Preservation guard** (test-first): every outline writer carries an existing
   `turns` block across a regeneration — `dev/scripts/lib/outlineTurns.js` for
   the JS writers, `preserve_turns()` for `average_trajectory_outline.py`.
4. `register_outline.py` rejects a malformed `turns` block.
5. `dev/scripts/test_outline_turns.js` wired into `npm test` and
   `testFeatures["map-turn-names"]`.
6. No UI change: the renderer is slice 03.
