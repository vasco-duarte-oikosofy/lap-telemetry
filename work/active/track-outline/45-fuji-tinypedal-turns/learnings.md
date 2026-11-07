# Learnings — Slice 45 (why a map can silently have no turn labels)

- **"The names don't show up" is a data-pipeline question, not a rendering
  question.** The map code was fine: there was no `Fuji Speedway.turns.json` in
  TinyPedal at all. Before touching a painter, check that the packaged data file
  for that exact map name exists — and remember TinyPedal matches map names
  ignoring accents/case/punctuation, so `Fuji Speedway` ≠ `Fuji Speedway Classic`.

- **A naming inconsistency had a data consequence.** `bake_outline_turns.py`
  resolves `<slug>.json`; the Fuji base outline is `<slug>_outline.json`. The
  baker reported "no outline" and moved on, so the outline never got a `turns`
  block, and the exporter (which only exports outlines that already have turns)
  skipped it. Two "skip" messages that each looked harmless produced a silently
  label-less map. The fix is a 2-line resolver, but the lesson is to treat a
  build step's `skip` line as suspicious, not as noise.

- **The legacy names are already known debt.** The map-turn-names backfill notes
  (`04-backfill-tracks`) list `bahrain_outline`, `fuji-speedway_outline` and
  `circuit-de-barcelona-median` as "no coaching model for that slug". The
  architecture review flags the `staticFujiSpeedway_outlineOutlineData.js` name.
  This slice fixes the *behaviour* (bake resolves the legacy file) without
  buying into the rename refactor.

- **The denominator decides where labels land.** The base outline's geometric
  centreline is 4489.5 m; the model's simulator axis is 4538.9 m. Exporting
  `apex_s_m / geometric_length` placed Panasonic at 0.8177 instead of 0.809 —
  ~50 m late. Stamping `lap_length_m` from the coaching model (as Long Beach and
  Paul Ricard 1A already do) keeps the label axis identical to the corner axis.
  Worth checking whenever an outline carries `apex_s_m` but no `lap_length_m`.

- **The Classic layout still has this bug** (`Fuji Speedway Classic.turns.json`
  was exported with 4464.5 m, its model axis is 4510.1 m). Fixing the base
  layout without touching Classic is deliberate scope control, but the deferred
  item is recorded in the handoff — otherwise it will be rediscovered as a
  "labels are slightly off" complaint.

- **Placeholder-name detection can hide real names.** The shared rule
  `^turn \d+$` treats Fuji's official "Turn 11"/"Turn 12" as generated
  placeholders, so the outline stores `name: null`. The curated `short_name`
  (`Eleven`/`Twelve`) saves the map, and the coaching model keeps the official
  name — but a track whose official names are literally numbered corners will
  always lose the `name` field. Prefer `11th Corner` style if it matters.

- **A test that pins names/apexes/display labels per track is the cheapest
  guard for this whole class.** Extending `test_outline_turns.js` with one entry
  (`fuji-speedway`) failed immediately before the bake and pins the outcome
  afterwards, including the fact that the outline file uses a legacy name.
