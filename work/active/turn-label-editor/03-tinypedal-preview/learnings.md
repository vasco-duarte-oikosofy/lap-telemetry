# Learnings — Slice 03 (TinyPedal preview tab)

- **Two "rotation" conventions looked the same at 0° and diverged at any other
  angle.** The editor rotated counter-clockwise for a positive angle; TinyPedal's
  `rotate_coordinate` runs in a y-down frame, so positive is clockwise. At 0° the
  two frames agreed exactly (bearing 158.24° both), which is exactly why the bug
  survived: every check anyone runs first is the unrotated one. Measure at a
  non-zero angle — comparing a bearing at +30° exposed it in one line.

- **Fixing the convention is a data migration, not a code change.** Placement
  offsets are rotation-independent (map-space metres), so only the stored angle
  had to flip: the driver's Imola `-96` becomes `+96` and the picture is
  identical. That is why the export format went to `version: 3` and
  `version < 3` negates the angle on import — old files stay usable without
  asking the driver to re-place anything.

- **The editor should adopt the consumer's convention, not its own.** It existed
  to produce a number for TinyPedal; keeping a "prettier" internal convention
  meant every export needed a manual sign flip. One `toDisplay()` (negate Y) made
  the slider value directly usable.

- **A faithful preview is cheap when the source is a small well-factored module.**
  `turn_labels.py` takes `measure` as a callback ("nothing here imports Qt"), so
  the whole placement rule ports to canvas in ~60 lines with `ctx.measureText`.
  Reading the widget's config defaults (`area_margin 40`, `font_ratio 0.023 ×
  font_scale 1.6`, `nudge_steps`) made the preview honest instead of approximate.

- **TinyPedal's map is our outline with Y negated.** Verified: outline first point
  `(8.0, 843.8)` vs SVG `(-2.2, -844.8)`; farthest point `(504.3, 212.5)` vs
  `(506.2, -205.9)`. So a placement offset in sim metres converts to the widget's
  units as `(dx, -dy) × (tinyLength / lap_length_m)` — no fitted transform needed.

- **Not every outline is named like its LMU track.** `silverstone-grand-prix-circuit---elms`
  has `track_name: "Silverstone Circuit"` while the map/label files are keyed by
  `"Silverstone Grand Prix Circuit - ELMS"`; the generator now tries
  `track_name_mapping.canonical_lmu_track_name` too. 18 of 19 tracks have a
  recorded map; the odd one out is that outline.

- **`s_frac` belongs to the packaged label file, not to us.** The widget anchors
  on the fractions in `turn_labels/<track>.turns.json`; recomputing them from
  `apex_s_m / lap_length_m` would drift whenever a model's `lap_length_m` and the
  outline's axis disagree (Imola's outline has none at all). The generator embeds
  the packaged values and only falls back when they are missing or misaligned.
