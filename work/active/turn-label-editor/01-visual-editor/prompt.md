# Slice 01 — visual turn-label editor

Status: ✅ Complete — `dev/tools/turn-label-editor.html` (19 tracks, drag + rotation + JSON export)
Trigger: *"I need a visual editor for the placement of the corner names on the
tinypedal map. create a simple html under dev/ where I can load any track's
layout+turns, and then drag and drop the corner name to the right place. add also
a rotation slider, so that I can rotate the track into the right position so that
it fits better the screen when LMU is running."*

## Goal

`dev/tools/turn-label-editor.html` — one file, opened with a double click
(`file://`, no server), that:

1. lists **every** track outline in `product/data/track-outlines/` (30 today) and
   draws the selected layout's centreline plus its corner names;
2. lets each corner name be **dragged** anywhere, with the position remembered
   per track and per label;
3. has a **rotation slider** (`-180…+180°`) that rotates the layout while every
   label stays upright and attached to its corner;
4. shows, and offers for copying/download, the placement as JSON.

## Design decisions

- **Generated, not fetched.** A `file://` page cannot `fetch()` the outlines, so
  `dev/scripts/build_turn_label_editor.js` inlines a compact payload (slug,
  names, `lap_length_m`, centreline, turn anchors) and the test fails if the
  committed HTML is not exactly what the generator produces.
- **Offsets are map-space metres**, relative to the turn's own anchor point, so
  they survive canvas size, zoom and rotation. Rotation is stored as
  `display_orientation` — the same setting TinyPedal's track map widget already
  takes (`wcfg["display_orientation"]`), so the slider's value is directly
  usable.
- **Nothing is written into `product/`.** This slice is a tool; wiring the export
  into `export_turn_labels_for_tinypedal.py` and the widget is a later decision
  (the label-offset schema has to be agreed with TinyPedal first).

## Acceptance

- [ ] The page loads, and switching the track select redraws layout + labels for
      every one of the 30 outlines with no console error.
- [ ] Dragging a label moves it; the offset survives a track switch away and
      back (localStorage), and "Reset" puts it back on its anchor.
- [ ] The rotation slider rotates the layout, labels stay horizontal and stay
      attached to their corners.
- [ ] The JSON panel shows the current placement and "Copy" copies it.
- [ ] `bash scripts/test-summary.sh --feature turn-label-editor` exits 0,
      including a freshness test (regenerating reproduces the committed file).
- [ ] `npm run build` still succeeds and `dist/compare.html` is unchanged.
- [ ] `handoff.md` + `learnings.md`; PLAN.md row updated.

## Boundaries

- No changes to `product/data/`, the widget, or the TinyPedal repo.
- No new runtime dependency, no bundler, no framework: plain HTML + canvas.
- The generated HTML must stay under the 437-line file ceiling.
