# Handoff — Slice 06 (TinyPedal port)

## What is on disk

### In `../tinypedal` (commit `40cb63d0`)

| Path | What it is |
|---|---|
| `tinypedal/turn_labels.py` | **new** — Qt-free planner + data loader: `font_size`, `turn_texts`, `anchor_from_fraction`, `outward_normal`, `anchor_turns`, `plan_turn_labels`, `load_turn_labels`, `default_data_path`. `TURN_LABEL_CONFIG["font_scale"] = 1.6` gives the widget 60 % larger type than the compare app. |
| `tinypedal/widget/track_map.py` | loads the label data with the map, draws labels into the map pixmap after the sector lines (`draw_turn_names`), tracks `map_orient_deg`, ends the painter. Text is filled **and** stroked in `turn_name_color` (`TURN_SOLIDIFY_EM = 0.085`), halo is an outside-only ring (`TURN_HALO_EM = 0.06`) painted after the text. |
| `tinypedal/template/setting_widget.py` | 3 new options: `show_turn_name` (True), `turn_name_color` (#CCCCCC), `turn_name_outline_color` (#88000000). |
| `tinypedal/data/turn_labels/*.turns.json` | **new** — 14 tracks, 173 corners, generated. |
| `.gitignore` | re-includes the data folder and the three tests (negations must stay after `/trackmap/`, `*.json`, `test*.py`). |
| `tests/test_turn_labels.py` | layout rule on synthetic tracks (30 assertions). |
| `tests/test_turn_labels_render.py` | all 14 shipped tracks rendered headless. |
| `tests/test_track_map_widget_labels.py` | the real widget class, pixel-level. |
| `docs/customization.md`, `CLAUDE.md` | the three options + how to regenerate the data. |

### In this repo

| Path | What it is |
|---|---|
| `dev/scripts/export_turn_labels_for_tinypedal.py` | exporter (`--out`, `--trackmap`, `--check`); writes `tinypedal/tinypedal/data/turn_labels/`. |
| `dev/scripts/test_tinypedal_turn_label_export.py` + `.js` | schema/geometry/staleness tests via a Node wrapper. |
| `dev/scripts/test_turn_labels_parity.js` | JS vs Python planner parity. |
| `docs/specs/MAP_TURN_NAMES.md` | "The TinyPedal port" section. |
| `work/active/map-turn-names/06-tinypedal-port/artifacts/*.png` | review images: 14 tracks at 400 px, plus the real widget at 0°/90°. |

## Verified

- TinyPedal: `test_turn_labels.py` PASS, `test_turn_labels_render.py` PASS
  (400 px: **170/173 corners, 126/136 names**; 600 px: **173/173, 133/136**;
  0 overlaps, 0 off-canvas), `test_track_map_widget_labels.py` PASS (type
  11.8 px, halo inflation +22 %, label pixels present in the saved image).
- The render tests refuse to run when Qt has no font database — check
  `QFontDatabase().families()` if an image looks like tofu boxes.
- This repo `--feature map-turn-names`: **314 assertions, 9 scripts, ALL PASS**.
- Parity: JS and Python planners agree to **0.000000000 px** on four map sizes.

## How to keep it in sync

```bash
py dev/scripts/export_turn_labels_for_tinypedal.py           # regenerate
py dev/scripts/export_turn_labels_for_tinypedal.py --check   # CI-style check
node dev/scripts/test_turn_labels_parity.js                  # after touching either planner
```

## Known limits

- Anchoring assumes the recorded map starts at the start/finish line (it does —
  TinyPedal records one lap from the line). A map recorded from a rolling start
  elsewhere would offset every label by the same fraction of the lap.
- At the default 400 px widget, 60 % larger type costs 3 labels and 10 names on
  the most crowded tracks (Silverstone GP, Paul Ricard 1A-V2). Raise `area_size`
  to ~600 px to get 173/173 and 133/136 back; the type is capped by `font_size`
  (default 15 px), so a bigger widget gains room without gaining type size.
- The label data is per track name; a track that is in our outlines but has no
  TinyPedal map is skipped by the exporter (none today).

## Follow-up fix (bug 31, after sign-off)

The labels were approved by size but then reported as outlines. Fixed in place:
solid fill (self-stroke), outside-only halo ring, and `turn_name_color` default
`#FFFFFF`. **Existing presets keep `#CCCCCC` — set it to `#FFFFFF` or delete the
key.** See `work/active/bugs/31-turn-label-text-outline-only/bug.md`.
