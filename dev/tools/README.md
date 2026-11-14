# dev/tools/

Development tools live here.

Use this folder for browser helpers, validation pages, diagnostics, and one-off utilities that support development but are not part of the production product boundary.

## Track outline generation

See [`README-GENERATE-OUTLINE.md`](README-GENERATE-OUTLINE.md) for the detailed workflow to generate and register a new track outline from simulator trajectory/session data. That guide covers the required data, scripts, validation, and rebuild steps.

## Reference lap export

See [`README-REFERENCE-LAPS.md`](README-REFERENCE-LAPS.md) for how to regenerate the reference lap parquets in `product/data/reference-laps/` — one fastest-clean-lap per track, named with the vehicle slug so users know which car produced the lap.

## Turn label editor (corner names on the map)

[`turn-label-editor.html`](turn-label-editor.html) places the corner-name labels
that TinyPedal draws on its track map. Open it with a double click — it is a
single file with every outline inlined, so it works over `file://` with no
server and no build step at run time.

- Pick a track, drag a name to where it belongs, click one and nudge it with the
  arrow keys (Shift = 10×).
- The rotation slider is TinyPedal's `display_orientation`; use it to turn the
  layout so it fits the LMU screen. Labels stay upright and stay attached to
  their corner.
- Placements are remembered per track in `localStorage`; **Copy JSON** /
  **Download JSON** give you `{track, display_orientation, labels: {id: {dx_m,
  dy_m}}}` — offsets are metres from each corner's anchor, so they do not depend
  on canvas size, zoom or rotation.
- **Reset this track** / **Reset all** clear the overrides.

It is generated from `turn-label-editor.template.html` plus
`product/data/track-outlines/*.json`:

```bash
node dev/scripts/build_turn_label_editor.js          # regenerate after an outline change
node dev/scripts/build_turn_label_editor.js --check  # verify the committed file is current
```

`test_turn_label_editor.js` fails if the committed HTML is stale, so run the
generator after re-baking any outline's turns.

Note: this slice only produces the placement. Feeding the offsets back into
`dev/scripts/export_turn_labels_for_tinypedal.py` and the widget is not wired
yet — the label-offset schema has to be agreed with TinyPedal first.
