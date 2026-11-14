# Slice 02 — drag-direction fix, import, and the driver's Imola placement

Status: ✅ Complete
Trigger: *"1. the up and down directions with mouse are reversed, when I drag down,
the lable moves up. Left and right are correct. 2. here's the right Imola layout
and rotation: imola-rotated.json"*

## What was wrong

`draw()` placed a label at `ay + oy * scale` while every other path treats sim Y
as up (`toScreen` uses `ay - ry * scale`). So the label rendering was mirrored
vertically: dragging down produced a negative map-space `dy` (correct) that was
then drawn upwards. Horizontal was unaffected. The existing test only checked
that an offset was *non-zero*, so it never noticed.

Consequence for the driver's own export: the stored `dy` values are what looked
right **under the mirrored renderer**. Rendering them with the fix would mirror
them around each corner, so the placement file needed a repair, not just a replay.

## Goal

1. Fix the vertical direction (and pin both directions in the test).
2. Make a placement file loadable: an **Import** control plus drag-and-drop.
3. Ship the driver's Imola placement as the default for that track, repaired.

## Decisions

- Export format is now **version 2**. `version: 1` files are converted on import
  with a rotation-aware repair — mirror the rotated vector's Y and rotate back —
  which restores exactly what the driver saw, at any `display_orientation`.
- The repair lives in the import path, so the preset file stays the driver's
  **verbatim export** (`dev/tools/turn-label-presets.json`, `version: 1`) and the
  conversion is one code path for both importing and shipping.
- `Reset this track` now restores the shipped preset when one exists (a reset
  that silently threw away the driver's placement would be a trap).
- The tool was split into `turn-label-editor.js` (app) +
  `turn-label-editor-ui.js` (controls/import/boot) + generated
  `turn-label-data.js`, because the single generated file was sitting exactly on
  the 437-line ceiling. Classic scripts, so `file://` still works — now covered
  by an explicit `file://` smoke test.

## Acceptance

- [x] Drag down → label moves down; drag right → label moves right (asserted).
- [x] Import applies track + rotation + offsets; a foreign JSON is refused with
      a visible reason; a v1 file gets its `dy` repaired.
- [x] Imola opens at −96° with all 11 names placed, zero overlaps.
- [x] Placement survives a reload; Reset restores preset or blank.
- [x] `--feature turn-label-editor --pw` and the full `--pw` suite green;
      `dist/compare.html` unchanged.
