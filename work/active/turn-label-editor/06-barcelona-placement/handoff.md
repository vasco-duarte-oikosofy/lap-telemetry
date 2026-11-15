# Handoff — Barcelona placement and TinyPedal-only test rule

## Delivered

- Archived the exact driver's v3 input in `artifacts/driver-placement.json`.
- Added `circuit-de-barcelona` to `dev/tools/turn-label-presets.json`: 0° and
  all 14 offsets unchanged. Rebuilt `dev/tools/turn-label-data.js`.
- Targeted export updated only sibling
  `tinypedal/data/turn_labels/Circuit de Barcelona.turns.json`.
- Added exact-input assertions in `test_shipped_turn_label_placements.js` and
  browser reset/export coverage in `test_turn_label_editor.js` (Barcelona is
  no longer an unplaced track).
- Sibling `tests/test_shipped_placements.py` now covers Barcelona and creates
  real 400/600 px widgets. Commit: `a5cf854e` on TinyPedal `master`.
- Created `docs/HOW_TO_UPDATE_TINYPEDAL_MAP.md`, linked from `AGENTS.md`, the
  tooling README and mission plan. Removed obsolete README schema/unwired text.
- At the user's explicit request, AGENTS.md now requires **ONLY TinyPedal
  tests for TinyPedal updates**, overriding feature/full-suite/milestone and
  infrastructure-guard requirements. Runbook and this slice prompt match.

## Verification

- Initial failing test: 21 expected failures before shipping the placement;
  see `artifacts/test-first-red.txt`.
- Final focused TinyPedal placement wrapper: **92 assertions passed**.
- Final focused TinyPedal export wrapper: **23 assertions passed**.
- Targeted exporter `--check` and editor generator `--check`: clean.
- `npm run build`: passes; `product/dist/compare.html` current, no diff.
- Real Qt Barcelona 400/600 px: all 14 labels rendered, none dropped,
  zero overlaps, all inside widget, rotation 0, painted ink. Review PNGs in
  artifacts; 400 px image inspected.
- Scope audit: only Barcelona's sibling payload changed among the audited
  curated product data and all packaged TinyPedal labels. Existing dirty
  references/models/tests/package.json and other work were left untouched.

## Historical broad runs (before the user's test-rule change)

Feature suite passed: 301 assertions / 7 scripts. The already-started full
suite finished with 3 failing unrelated scripts: `test_delta_time_gains.js`,
`test_js_pipeline_contract.js`, and
`test_generate_track_coaching_model_from_reference.js`. These were already
modified in the working tree at start and concern the separate Barcelona
reference refresh. They were not changed or repaired here. Historical logs are
retained; the new TinyPedal-only policy requires no broad rerun.

## Activation / flags

No runtime code or user settings were changed. TinyPedal uses the packaged
orientation when `use_track_orientation=true` and `display_orientation=0`;
a nonzero user orientation still wins. `show_turn_name` must be enabled.
Restart TinyPedal or reload its map widget to discard cached data.

Live-driver confirmation is pending; automated QA is complete. No planner,
reference, model, outline or other-track work is deferred into this slice.
