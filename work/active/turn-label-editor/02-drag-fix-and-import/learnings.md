# Learnings — Slice 02 (drag fix, import, Imola preset)

- **A mirror bug can hide behind a "does it move?" test.** The slice-01 test
  asserted that a drag produced a *non-zero* offset, so an inverted axis passed.
  Pin the **direction** — drag down → the box's `y` increases *and* the stored
  `dy` decreases (map Y is up) — otherwise a sign error is invisible.

- **Fixing a renderer retroactively changes stored data.** Because labels were
  drawn Y-mirrored, every placement file made before the fix encodes
  "what looked right under the buggy renderer". Replaying it after the fix
  mirrors it around each anchor. The repair is a rotation-aware Y mirror
  (`rotate(dx,dy,θ)`, negate Y, rotate back by `−θ`); a plain `dy → −dy` is only
  correct at `rotation = 0`. Export format went to `version: 2` so the old files
  are identifiable, and the *preset file* deliberately stays `version: 1` so the
  same repair runs for imports and shipped defaults.

- **`Reset` must not throw away a shipped preset.** Once a track can open
  pre-placed, "reset" meaning "blank" would delete the driver's work on the next
  click. Reset now means "back to the shipped placement", or blank if there is
  none.

- **The 437-line ceiling is a design signal, not an obstacle.** The single
  generated file sat exactly at 437; the answer was not to minify but to split
  along a real seam: data (generated) / app (state, geometry, drawing) /
  ui (controls, import, boot). 68 + 313 + 138 + 4 lines now, each with room.

- **`file://` and classic scripts:** splitting into several files is safe as long
  as they are plain `<script src>` — ES modules would fail on a `file://` page
  because of CORS. The test now loads the real `file://` URL, so the
  double-click promise is covered.

- **Import validation pays for itself immediately**: an unrelated JSON dropped on
  the page would otherwise silently overwrite a track's placement. Check
  `tool`, `track` and `labels`, and say *why* it was refused in the status line.

- **Presets are the bridge until TinyPedal reads offsets.** Shipping the driver's
  export in `turn-label-presets.json` makes a good placement the default on every
  machine without touching the widget — cheap, and reversible if the schema
  lands differently later.
