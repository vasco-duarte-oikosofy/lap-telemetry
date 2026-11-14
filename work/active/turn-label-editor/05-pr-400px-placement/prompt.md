# Slice 05 — the Paul Ricard ELMS placement checked at 400 px

Status: ✅ Complete
Trigger: *"ok. here's the one checked at 400px preview"* —
`turn-labels-paul-ricard---elms (1).json` (version 3, 0°, 16 labels).

## Goal

Ship the re-tuned Paul Ricard ELMS placement **and** make sure the 400 px check
it was tuned against told the truth.

## What was found

The preview tab measured labels with the page's UI font. The widget draws them in
**Consolas Bold** at `min(font_size(area − 2·margin), max(font_size, 5))` px and
reserves a `0.085 em` self-stroke when measuring. Consolas is ~30 % wider than the
UI font, so the preview under-reported width: a layout that looked clear at 400 px
was overlapping in the real widget (3 pairs, one by 25 px).

Two fixes, plus a behaviour change so a placement still wins where it can:

1. **Preview font fidelity** — `turn-label-editor-preview.js` now draws and
   measures with `bold <px> Consolas, monospace` and adds the stroke to every
   width, exactly like `QFontMetricsF` + `turn_solidify_width`. The status line
   names the font so the eyeball knows what it is judging.
2. **Stretch before fallback** — a placed label that collides is now slid further
   out along the side the driver chose (×1.0 → ×2.4 of its offset) before the
   widget hands that corner back to its own rule. Their side and rough distance
   survive; only readability decides.
3. **Test-harness fidelity** — `tests/test_turn_labels_render.py` now passes
   `units_per_metre` (the real widget does) and can drive the packaged
   orientation; without that the sibling tests were measuring a slightly
   different placement than the widget performs.

## Result (real widget, Qt metrics)

| Widget size | Labels | Dropped | Placement stretch |
|---|---:|---:|---|
| 400 px | 16/16 | 0 | median 1.00, max 1.40 (2 labels > 1.15) |
| 600 px | 16/16 | 0 | median 1.00, max 1.79 (3 labels > 1.15) |

No overlaps, everything inside the widget, both sizes.

## Acceptance

- [x] New placement packaged (`label_offset_m` + `display_orientation: 0`) and
      drawn by the widget; `export_turn_labels_for_tinypedal.py --check` clean.
- [x] Preview uses the widget's font and stroke; the 400 px view matches Qt.
- [x] All sibling turn-label tests pass (8 files), plus the placement contract.
- [x] `--feature turn-label-editor --pw`, full `--pw` suite green; bundle unchanged.
