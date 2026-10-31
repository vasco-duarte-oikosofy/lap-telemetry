# Slice 06 — Render turn names in `../tinypedal`'s track map

Port the reviewed label layout to the TinyPedal Qt widget: same rule, smaller
map (100–400 px), different painter, and no shared coordinate system with the
compare app.

Deliverables:
1. `tinypedal/turn_labels.py` — pure planner (no Qt imports, injected metrics):
   `font_size`, `turn_texts`, `anchor_from_fraction`, `outward_normal`,
   `anchor_turns`, `plan_turn_labels`, `load_turn_labels`.
2. Data per track with `s_frac`, generated here by
   `dev/scripts/export_turn_labels_for_tinypedal.py`, shipped in
   `tinypedal/tinypedal/data/turn_labels/`.
3. Widget integration in `tinypedal/widget/track_map.py` + three options in
   `tinypedal/template/setting_widget.py`.
4. Tests: layout rule, all shipped tracks rendered, real widget class; plus a
   cross-language parity test from this repo.
