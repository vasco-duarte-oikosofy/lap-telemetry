# Handoff — Slice 01: visual turn-label editor

## What exists now

`dev/tools/turn-label-editor.html` — **double-click it**, no server needed.

| Control | What it does |
|---|---|
| Track select | all **19** outlines that have baked turn anchors (the 9 that do not are excluded) |
| Rotation slider + number box | `-180…+180°`, exported as TinyPedal's `display_orientation` |
| Zoom / font size / text mode | `Number + name`, `Name`, `Number`; 9–26 px; 50–200 % |
| Drag a name | moves that corner's label; the offset is stored per track |
| Arrow keys | nudge the selected label 1 px (Shift = 10×) |
| Copy / Download JSON | the placement below |
| Reset this track / Reset all | clears the overrides |

Placements live in `localStorage` under `turnLabelEditor.v1`, so they survive a
reload and a track switch. The JSON panel at the bottom is always current:

```json
{ "tool": "turn-label-editor", "version": 1,
  "track": "silverstone-national-circuit", "track_name": "Silverstone National Circuit",
  "layout": "national", "lap_length_m": 2639.1, "display_orientation": 0,
  "label_text": "number-name", "font_px": 13,
  "labels": { "copse": { "dx_m": 0, "dy_m": 12.8 }, ... } }
```

`dx_m` / `dy_m` are **metres in the outline's map space, relative to the corner's
own anchor** — they do not depend on canvas size, zoom or rotation, which is why
a label keeps its place while you turn the map.

Screenshots of two real tracks in `artifacts/` (`editor-paul-ricard.png` at 32°,
`editor-silverstone-national.png`).

## Files

| File | Role |
|---|---|
| `dev/tools/turn-label-editor.html` | **generated**, committed, 437 lines / 203 KB, all 19 layouts inlined |
| `dev/tools/turn-label-editor.template.html` | the source — edit this, not the generated file |
| `dev/scripts/build_turn_label_editor.js` | template + `product/data/track-outlines/*.json` → HTML; `--check` verifies freshness |
| `dev/scripts/test_turn_label_editor.js` | 30 assertions: static contract, freshness, and a real Playwright run |
| `dev/tools/README.md` | how to open it, regenerate it, and what is still unwired |
| `package.json` | feature `turn-label-editor` (6 scripts) + the test in `npm test` |

Regenerate after **any** outline change:

```bash
node dev/scripts/build_turn_label_editor.js          # writes the tool
node dev/scripts/build_turn_label_editor.js --check  # CI-style: fails if stale
```

## How placement works

Labels the user has not moved are auto-placed: a candidate fan around the corner
(8 distances out along the outward normal × 2 sides × 9 steps along the local
tangent), first candidate that is on-canvas and collides with nothing already
placed wins. It is computed against the **unrotated** view and cached per
(track, text mode, font, zoom, canvas size), so rotating the map does not
re-shuffle the layout — labels turn with the track as a rigid body.

Dense layouts still start with some collisions, and that is accepted: the test
requires **≥ 60 % of names clear at open**, and the worst layouts are La Sarthe
12/19, Fuji 7/11, Paul Ricard 1A 8/14, Paul Ricard ELMS 11/16. Every track's
first placement is at least 57 % clear, most are 100 % (Barcelona, Monza,
Sebring, Silverstone National and International, Laguna Seca, Paul Ricard 3A).
A perfect auto-layout was not the goal — the editor exists so the last few are
placed by eye.

## Deliberately NOT done

**Nothing feeds these offsets back into TinyPedal yet.** The export JSON exists,
but `export_turn_labels_for_tinypedal.py` still publishes only `s_frac` per turn,
and the widget (`tinypedal/turn_labels.py::plan_turn_labels`) computes its own
placement at run time. Wiring this up needs a schema decision in the sibling
repo — e.g. an optional `label_offset_m: [dx, dy]` on each turn in the packaged
`.turns.json`, applied as the *preferred* candidate before the planner's own fan.
That is a TinyPedal slice, not this one.

Also not done: the 9 outlines without baked turns (Monza base, Spa, COTA,
Bahrain, Lusail, Algarve, Barcelona-median, …) are not in the picker — there is
nothing to place. They appear in the generator's "have no turns" count.

## Verified

- `bash scripts/test-summary.sh --feature turn-label-editor --pw`: **190
  assertions / 6 scripts — ALL PASS**.
- Full `bash scripts/test-summary.sh --pw`: **2901 assertions / 99 scripts — ALL
  PASS** (was 2862 / 98).
- `npm run build` succeeds; `dist/compare.html` unchanged (this slice touches no
  product asset).
- The browser test drives the real page: 19 options, six Silverstone National
  labels drawn, a drag recorded and exported, 45° via the slider and −90° via the
  number box, offset invariant in metres across rotations, placement + rotation
  surviving a reload, Reset clearing it, a painted canvas, and no console errors.

## Next steps (suggested, in order)

1. Use it on `paul-ricard---elms` (the track whose label gate just bit us) and
   `circuit-de-la-sarthe` (19 turns, the densest map) and see whether the
   exported offsets are good enough to want them shipped.
2. Then open the TinyPedal slice: extend the packaged label schema with an
   optional offset and make `plan_turn_labels` honour it before its own fan.
3. Only after that: teach `export_turn_labels_for_tinypedal.py` to merge an
   editor export into the packaged file.
