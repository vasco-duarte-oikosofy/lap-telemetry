# Learnings — Slice 04 (placements shipped into TinyPedal)

- **A placement is only useful if the consumer can express it.** The packaged
  `*.turns.json` needed two extra keys (`label_offset_m`, `display_orientation`)
  and the widget needed `TurnAnchor.offset` — three small changes beat one clever
  side-channel (a config file, a global, a filename convention).

- **Convert offsets where the map is transformed, not where they are read.**
  `anchor_turns` already rotates and scales the anchors, so it converts the
  placement with exactly the same rotate-then-scale (`units_per_metre` from
  polyline length ÷ lap length, and sim Y negated because TinyPedal maps are
  y-down). Doing it anywhere else would drift on rotated maps.

- **The widget clamped negative rotations to 0** (`max(int(display_orientation),
  0)`), which would have silently turned Imola's −89° into 0°. Found by shipping a
  negative value; `rotate_coordinate` handles any angle, the clamp was just
  defensive.

- **A placement can be worse than the rule at a different widget size.** The
  driver tuned Paul Ricard ELMS in the editor (~900 px canvas); at the widget's
  400 px default two labels collide because the text stays ~12 px while the map
  shrinks. Hence the rule: honour the placement unless it overlaps or leaves the
  widget, then fall back per corner. That keeps the "no overlapping labels" gate
  meaningful at every size instead of asking the driver to re-tune per size.

- **Don't let a per-track default silently fight a user setting.** The packaged
  orientation is used only while `display_orientation` is at its default 0, with
  `use_track_orientation` to opt out. Any non-zero user value wins. Anything more
  clever (e.g. "0 means unset") cannot be expressed with an int setting.

- **Existing tests were testing the planner, not what ships.** With placements in
  the data, the four per-track tests started measuring something else. Splitting
  them (`ignore_placements=True` keeps them on the rule; `test_shipped_placements.py`
  covers the placement contract) keeps both contracts honest.

- **Watch out for async in browser tests**: `file.text()` in the import handler
  means `setInputFiles` returns before the placement is applied. Wait for the
  status line, not a timeout — the earlier flakes in this slice were exactly that.

- **Sibling-repo test discovery is path-sensitive.** The per-track widget tests
  take `--outline` from *this* repo; their default slug guesses (`paul-ricard-elms`)
  do not match the outline filenames (`paul-ricard---elms`), so spell the path out
  when running them by hand.
