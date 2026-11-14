# Slice 03 — TinyPedal preview tab

Status: ✅ Complete
Trigger: *"create a tab where I can render the map just like tinypedal would, so
that I can eyeball the rotation and turn label placement"*

## Goal

A second tab in the editor that draws what the **live widget** will draw, so
rotation and label placement can be judged without starting LMU:

- TinyPedal's **own recorded map** (`../tinypedal/trackmap/<track>.svg`), not our
  outline — that is the shape the overlay paints;
- its `display_orientation` rotation and `scale_map` fit (square widget, 40 px
  margin, shorter axis centred);
- its `anchor_turns` rule: corners anchored by `s_frac` on the recorded polyline,
  outward normal from the map centroid;
- its `font_size` rule and `plan_turn_labels` placement (odd turns outside, even
  inside, text degrades before it moves, no overlaps);
- **the editor's placement applied on top**, converted into the widget's frame;
- widget size selector (250/400/600/800 px) and corner dots.

## The rotation-convention problem this exposed

The editor rotated the map the *opposite* way round from TinyPedal: a positive
angle was counter-clockwise on screen, whereas `rotate_coordinate` in TinyPedal's
y-down frame is clockwise. Verified numerically (bearing of Copse→Brooklands:
editor +0°/TinyPedal +0° agree at 158.24°, but at +30° they differ by 60°).

Fixed by adopting TinyPedal's convention in the editor itself (`toDisplay` negates
Y, then rotate in the y-down frame). Exported `display_orientation` is now the
number the widget takes, verbatim. Existing placement files are migrated on
import: `version < 3` gets its rotation negated, so the driver's Imola placement
still looks exactly as they approved it (‑96° there = **+96°** now).

## Acceptance

- [x] Preview renders TinyPedal's map for every track that has one (18/19; the
      Silverstone GP-ELMS outline has no map file, so it falls back and says so).
- [x] Preview rotates by exactly the exported `display_orientation`.
- [x] Placed labels come from the placement; the rest from TinyPedal's own rule.
- [x] Editor and preview agree: every label sits the same way round its corner in
      both tabs (asserted, worst < 25° across 11 Imola corners).
- [x] `--feature turn-label-editor --pw` and the full `--pw` suite green;
      `dist/compare.html` unchanged.
