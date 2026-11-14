# dev/tools/

Development tools live here.

Use this folder for browser helpers, validation pages, diagnostics, and one-off utilities that support development but are not part of the production product boundary.

## Track outline generation

See [`README-GENERATE-OUTLINE.md`](README-GENERATE-OUTLINE.md) for the detailed workflow to generate and register a new track outline from simulator trajectory/session data. That guide covers the required data, scripts, validation, and rebuild steps.

## Reference lap export

See [`README-REFERENCE-LAPS.md`](README-REFERENCE-LAPS.md) for how to regenerate the reference lap parquets in `product/data/reference-laps/` — one fastest-clean-lap per track, named with the vehicle slug so users know which car produced the lap.

## Turn label editor (corner names on the map)

[`turn-label-editor.html`](turn-label-editor.html) places the corner-name labels
that TinyPedal draws on its track map. Open it with a double click — the markup,
the app (`turn-label-editor.js` + `turn-label-editor-ui.js`) and the generated
data (`turn-label-data.js`) sit side by side and load as plain scripts, so it
works over `file://` with no server and no build step at run time.

- **Two tabs.** *Edit placement* is the working canvas (drag, nudge, zoom).
  *TinyPedal preview* renders the map the way the live widget will: TinyPedal's
  own recorded map SVG, its `display_orientation` rotation, its `scale_map` fit
  and margin, its font rule and its label planner — with your placement applied
  on top. Use it to judge rotation and label placement before touching the
  widget.
- Pick a track, drag a name to where it belongs, click one and nudge it with the
  arrow keys (Shift = 10×).
- The rotation slider **is** TinyPedal's `display_orientation`, with the same sign
  convention as the widget (positive = clockwise on screen), so the number can be
  pasted into the widget config. Labels stay upright and stay attached to their
  corner.
- Placements are remembered per track in `localStorage`; **Copy JSON** /
  **Download JSON** give you `{tool, version: 2, track, display_orientation,
  labels: {id: {dx_m, dy_m}}}` — offsets are metres from each corner's anchor, so
  they do not depend on canvas size, zoom or rotation.
- **Import JSON…** (or drop the file anywhere on the page) loads a placement
  back, switch to its track included. Placement files written before the Y-drag
  fix are `version: 1` and are repaired on import.
- **Reset this track** / **Reset all** restore the shipped placement for that
  track (see below), or a blank layout where none is shipped.
- Shipped placements live in [`turn-label-presets.json`](turn-label-presets.json)
  and are picked up by the generator, so a track can open already placed for
  every browser/machine. Today: Imola at ‑96° with all 11 names placed.

It is generated from `turn-label-editor.template.html` plus
`product/data/track-outlines/*.json`:

```bash
node dev/scripts/build_turn_label_editor.js          # regenerate turn-label-data.js
node dev/scripts/build_turn_label_editor.js --check  # verify the committed data is current
```

`test_turn_label_editor.js` fails if the committed data file is stale, so run the
generator after re-baking any outline's turns or editing the presets.

Note: this slice only produces the placement. Feeding the offsets back into
`dev/scripts/export_turn_labels_for_tinypedal.py` and the widget is not wired
yet — the label-offset schema has to be agreed with TinyPedal first.
