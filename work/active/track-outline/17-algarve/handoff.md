# Slice 17 — handoff

## State on disk

New:
- `product/data/track-outlines/algarve-international-circuit.json` — 500-point
  centreline + ±5 m boundaries, `lap_length_m` 4633.1, `source: Single lap
  trajectory`, no `turns` block.
- `product/web/js/staticAlgarveInternationalCircuitOutlineData.js` — generated
  ES module, export `ALGARVE_INTERNATIONAL_CIRCUIT_STATIC_OUTLINE`.
- `work/active/track-outline/17-algarve/` — this folder.

Modified (all by `register_outline.py` + `npm run build`):
- `product/web/js/trackOutlineManifest.js` — import + `OUTLINES` entry keyed
  `algarve-international-circuit`.
- `product/web/js/trackOutlineManifest_backup.js` — the script's own backup copy.
- `product/dist/compare.html` — rebuilt; contains the outline data.

## How it resolves

`findOutlineByTrackName()` returns the outline for both the LMU display name
(`Algarve International Circuit`) and the slug
(`algarve-international-circuit`). It does **not** resolve
`Algarve International Circuit ELMS` — see the open point below.

## Verified

- `bash scripts/test-summary.sh --feature track-outline --pw` → 1045 assertions,
  3 script failures, **all three pre-existing at `75eba85`**:
  `test_silverstone_national_p3.js` (needs `sessions/…` from the recording
  machine), `test_turn_labels_parity.js` (needs the sibling `../tinypedal`
  checkout), `test_turn_labels_scale.js` (the known 182/183 label failure).
- `npm run build` succeeds; `dist/compare.html` holds the outline data
  (`Algarve International Circuit` and the centreline coordinates are present).
- Manifest-driven tests (`test_static_outline_manifest_exports.js`,
  `test_static_track_outline_contract.js`, `test_track_name_inference.js`) pass —
  they enumerate `OUTLINES`, so the new entry is covered without a new test file.

## Deferred

- **`18-algarve-elms` is still open.** Both committed references carry
  `track_id = algarve-international-circuit` and lap lengths 4633.1 / 4638.7 m,
  so the evidence says one layout, one outline. But no ELMS-pack session exists
  on this machine, so the LMU track *name* for that pack is unverified: if it
  differs (e.g. `Algarve International Circuit - ELMS`), add it to
  `accepted_lmu_track_names` after recording one. Do not prefix-match it in.
- **No turn labels / anchors** — the Algarve coaching models still carry
  auto-generated names (`Turn 1…15`, plus a legacy 9-corner LMP2 model with every
  apex `right`). Curating Portimão's official names is its own slice and must run
  the guarded updater (`update_reference_and_coaching_model.py`), then re-bake
  turns into this outline with `bake_outline_turns.py`.
- **Live visual confirmation** — `visual_qa.status` is `pending`. Load a session
  on `file://product/dist/compare.html` and confirm the shell sits around the
  trajectory at the right scale (mission habit: automated render is not
  by-eye approval).
- `PLAN.md` rows for COTA GP, Le Mans, Lusail and Sebring are stale (outlines
  exist) — corrected in this slice, no data change.
