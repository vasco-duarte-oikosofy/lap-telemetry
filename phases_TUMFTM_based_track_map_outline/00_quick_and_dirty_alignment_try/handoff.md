# Handoff — Phase 00 Quick and Dirty TUMFTM Alignment Try

State on disk:

- `tools/manual_outline_align.html`
  - Standalone `file://` canvas alignment tool.
  - Loads simulator trajectory JSON, TUMFTM JSON/CSV, and optional extra trajectory JSON via file inputs.
  - Draws reference trajectory cyan, extra trajectories faint blue, TUMFTM centerline green dashed, left boundary yellow, right boundary red.
  - Supports scale/rotation/translation, flip x/y, reverse order, keyboard nudges, and export/copy/download of aligned outline JSON.
  - Reloads exported outline JSON as fixed already-aligned geometry.

- `scripts/prepare_manual_outline_inputs.js`
  - Converts TUMFTM `Spa.csv`-style `[x_m,y_m,w_tr_right_m,w_tr_left_m]` data to the simple JSON shape.
  - Exports one or more simulator lap trajectories from Parquet using `pos_x_m` and `pos_z_m` as `{ x, y }`.

- `scripts/test_manual_outline_align.js`
  - Playwright smoke test that loads minimal trajectory/track JSON into the standalone tool, exports JSON, parses it, and verifies centerline/left/right arrays exist.
  - Added to `npm test` in `package.json`.

Generated Phase 00 artifacts:

- `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/artifacts/tumftm-spa.json`
- `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/artifacts/spa-reference-lap8.json`
- `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/artifacts/spa-extra-lap9.json`
- `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/artifacts/aligned-outline-spike.json`
- `phases_TUMFTM_based_track_map_outline/00_quick_and_dirty_alignment_try/artifacts/alignment-overview.png`

Alignment used for the generated export:

```json
{
  "scale": 0.998,
  "rotation_rad": -0.0116,
  "translate_x": -154,
  "translate_y": 634,
  "flip_x": false,
  "flip_y": false,
  "reverse_point_order": false
}
```

Visual QA result:

- Agent visual assessment: Phase 00 is a clear win over the learned-boundary Spa artifacts.
- Bus Stop appears as a continuous believable corridor.
- La Source is smooth/plausible rather than jagged/noisy.
- Start/finish, Eau Rouge/Raidillon, Les Combes, and Bus Stop line up with the simulator trajectory in the overview.
- The optional extra lap sits inside or near the TUMFTM outline for most of the lap.
- The exported JSON parses and can be reloaded into the tool as already-aligned geometry.
- User validation was explicitly requested with the generated screenshot/export paths before closing the phase.

Verification:

- `node scripts/test_manual_outline_align.js` passes.
- `npm test` passes.
- `npm run build` passes and rewrote `dist/compare.html`.

Deferred:

- Do not integrate this into the compare UI in Phase 00.
- If continuing, Phase 01 should formalize the static outline contract from this exported shape instead of adding more editor behavior.
