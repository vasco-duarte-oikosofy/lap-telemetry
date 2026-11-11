# Slice 51 — Silverstone National Circuit / Ginetta P3 (new combo, full treatment)

Trigger: the driver ran Silverstone National Circuit in the Ginetta LMP3
(`sessions/session_20261111T172218Z_silverstone-national-circuit_lmu_practice.parquet`,
2026-11-11, LMU, `DKR Engineering #4:ELMS25` → catalogued slug `ginetta-lmp3`).
The track slug `silverstone-national-circuit` has **no** reference lap, coaching
model or outline; the existing Silverstone assets are other layouts
(`silverstone-grand-prix-circuit---elms`, `silverstone-international-circuit`)
and must not be aliased.

## Goal

Onboard `(silverstone-national-circuit, ginetta-lmp3)` end to end:

1. **Reference lap** — guarded export of the fastest complete valid lap.
2. **Coaching model** — official Silverstone National turn names for the 2.6 km
   National layout, with corner geometry taken from this lap's real
   speed/throttle/brake/steering signals.
3. **Track outline** — trajectory outline (500 points, synthetic ±5 m shell),
   `lap_length_m` on the same simulator distance axis as the model, official
   turn anchors baked in, registered in `trackOutlineManifest.js` + a static
   module, and `dist/compare.html` rebuilt.
4. **TinyPedal turn labels** — packaged `Silverstone National Circuit.turns.json`
   in the sibling `tinypedal` repo, derived from this outline.

## Layout facts to respect

The National layout is the short Silverstone loop: it does **not** use the
Arena complex (Abbey / Farm Curve / Village / The Link) that the International
layout shares with the GP circuit. It runs the National Straight, then the
classic Copse → Maggotts → Becketts → Chapel → Hangar Straight → Stowe → Vale →
Club loop and back onto the National Straight.

Names: Silverstone's own corner list / FIA turn-location plan. The GP/International
asset files for this circuit are the reference for spelling and the curated
`short_name` map conventions.

## Execution

1. Freeze/source-audit the session (no `lap_number` filtering; segment scan),
   record before-hashes, then run the guarded exporter and the folder validator.
   The National lap is ~51 s, which is below the exporter's hard 60 s lap floor —
   add an explicit, tested `--min-lap-time-s` override (default unchanged).
2. Read `TESTING_LESSONS.md`; add the failing reference/model/outline/resolver/
   TinyPedal tests **first** and register them in the `track-outline` feature
   suite.
3. Detect corners in scratch, review them against the real signals, then curate
   every official bend through a guarded one-shot initializer, following
   `create_paul_ricard_elms_assets.py`.
4. Bake turn anchors, generate the outline + static module, rebuild the bundle,
   export the TinyPedal labels (including the map start-line alignment check).
5. Validate references, `--print-facts`, feature suite, full `--pw` suite,
   build currency, scope audit; write `handoff.md` / `learnings.md`, mark the
   PLAN row, commit directly on `main`.

## Boundaries

- No changes to the Silverstone GP-ELMS / International assets, or any other
  track's reference, model, outline or TinyPedal labels.
- No raw `lap_number` filtering, no hand-copied reference, no snapshot merging.
- No original-recording cleanup; no `coach-race.log` inspection.
- Do not invent corners the lap does not have, and do not delete official names
  to make a test easier.
