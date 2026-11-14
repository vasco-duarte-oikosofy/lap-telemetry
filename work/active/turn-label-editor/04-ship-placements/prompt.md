# Slice 04 — ship the placements into TinyPedal

Status: ✅ Complete
Trigger: *"IMola / PAul Ricard ELMS / silverstone national / Monza Curva Grande —
update Tinypedal with these maps and turn label placements"* (four editor exports
`turn-labels-*.json`, all `version: 3`).

## Goal

The editor has been producing placements with nowhere to go. Ship them so the
live overlay draws the driver's layout instead of its own guess:

1. **Package the placements** — `dev/scripts/export_turn_labels_for_tinypedal.py`
   merges `dev/tools/turn-label-presets.json` into the packaged
   `<Track>.turns.json` as `label_offset_m` per turn (metres from the corner, sim
   Y up) plus the file-level `display_orientation` it was drawn for. Schema 2.
2. **Widget honours them** — `plan_turn_labels` places a turn with an offset at
   exactly that point; `track_map.py` rotates the map by the packaged orientation
   unless the user set one, and stops clamping negative angles to 0 (Imola ships
   ‑89°).
3. **Keep the quality gate** — a placement that would overlap an earlier one or
   leave the widget is handed back to the placement rule, so "zero overlapping
   labels" still holds at 400 and 600 px.
4. **Test the contract** in the sibling repo (`tests/test_shipped_placements.py`)
   and from here (`dev/scripts/test_shipped_turn_label_placements.js`).

## Acceptance

- [x] All four packaged files carry `label_offset_m` on every turn plus their
      `display_orientation`; `--check` clean, re-running byte-identical.
- [x] The widget draws them: 11/11 Imola, 16/16 Paul Ricard ELMS, 6/6 Silverstone
      National, 10/10 Monza — no overlaps, all inside the widget, at 400 and 600 px.
- [x] A user `display_orientation` still overrides the packaged one;
      `use_track_orientation: false` turns the package off entirely.
- [x] The four per-track sibling tests keep testing the automatic rule
      (placements stripped) and still pass at 0°/90°.
- [x] `--feature turn-label-editor --pw`, `--feature track-outline --pw` and the
      full `--pw` suite green; `dist/compare.html` unchanged.
