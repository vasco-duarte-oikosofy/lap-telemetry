# Handoff — Slice 05: Paul Ricard ELMS at 400 px

## Shipped

`dev/tools/turn-label-presets.json` → `paul-ricard---elms` replaced with
`turn-labels-paul-ricard---elms (1).json` (0°, 16 labels), re-exported into
`tinypedal/data/turn_labels/Paul Ricard - ELMS.turns.json`.

Real widget, Qt metrics:

| Size | Placed | Dropped | Stretch from the placed spot |
|---|---:|---:|---|
| 400 px | 16/16 | 0 | median 1.00, max 1.40 (2 > 1.15) |
| 600 px | 16/16 | 0 | median 1.00, max 1.79 (3 > 1.15) |

## Why the "400 px check" was misleading, and what changed

The preview tab measured text with the page's UI font. The widget uses **Consolas
Bold** plus a 0.085 em self-stroke, which is ~30 % wider, so the preview
under-reported label width and the same layout could overlap in the widget.

| File | Change |
|---|---|
| `dev/tools/turn-label-editor-preview.js` | draws/measures with `bold <px> Consolas` + stroke, like `QFontMetricsF`; status line names the font |
| `tinypedal/turn_labels.py` | a placed label that collides is stretched further out (×1.0 → ×2.4 of its own offset) before the corner is handed to the rule |
| `tinypedal/tests/test_turn_labels_render.py` | passes `units_per_metre` (as the widget does) and can drive the packaged orientation — the harness had been testing a slightly different placement than the widget performs |
| `tinypedal/tests/test_shipped_placements.py` | uses the packaged-orientation path |

## Notes

- **Stretch, not replace**: the widget now honours a placement wherever it can,
  nudging the label further out along the driver's chosen side. If you re-tune a
  track, tune it in the preview at the size you actually run (400 px default).
- The preview is a judge, not an oracle: canvas text metrics and Qt's
  `boundingRect` can still differ by a pixel, so a label that *just* fits may
  stretch slightly in the widget.
- Everything else from slice 04 stands: orientation packages, `use_track_orientation`,
  and the fallback rule.
