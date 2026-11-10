# Slice 50 — Paul Ricard - ELMS / Ferrari 296 GT3 (new layout, no assets)

Trigger: the driver ran the Paul Ricard ELMS practice session today
(2026-11-10, LMU, `session_20261110T175322Z_paul-ricard---elms_lmu_practice.parquet`)
in the Ferrari 296 GT3 `Vista AF Corse 2026 #21:LM` (catalogued slug
`ferrari-296-gt3`). Track slug `paul-ricard---elms` has **no** reference lap,
coaching model or outline; the existing Paul Ricard assets are the other
configurations (1A / 1A-V2-Short / 3A) and must not be aliased.

## Goal

Onboard `(paul-ricard---elms, ferrari-296-gt3)` end to end:

1. **Reference lap** — guarded export of the fastest complete valid lap.
2. **Coaching model** — official Paul Ricard turn names for the 5.8 km
   ELMS/1C configuration, with the genuinely flat (full-throttle) bends kept as
   `target_throttle_pct: 100` and corner geometry taken from this lap's real
   speed/throttle/brake/steering signals.
3. **Track outline** — trajectory outline (500 points, synthetic ±5 m shell),
   `lap_length_m` on the same simulator distance axis as the model, official
   turn anchors baked in, registered in `trackOutlineManifest.js` + a static
   module, and `dist/compare.html` rebuilt.
4. **TinyPedal turn labels** — packaged `Paul Ricard - ELMS.turns.json` in the
   sibling `tinypedal` repo, derived from this outline.

## Layout facts to respect

Measured against the curated 1A reference line, this lap leaves the 1A path in
exactly two places (max deviation 75 m and 67 m), which identifies the
**1C-V2 / ELMS configuration used by LMU**: the tighter Verrerie `S` and the
**Chicane Nord** pair in the middle of the Mistral straight. 1A has neither.
Everything else (Hôtel, Camp, Sainte-Baume, Signes, Beausset, Bendor, Garlaban,
Lac, Pont) is geometrically the same corners.

Official names (circuit `turnlocation.svg` plan + FIA turn-location list +
circuit track guide): `S de la Verrerie 1/2`, `Virage de l'Hôtel 1/2`,
`Virage du Camp`, `Virage de la Sainte-Baume`, `Ligne Droite du Mistral`,
`Chicane Nord 1/2`, `Courbe de Signes`, `Double Droite du Beausset 1/2`,
`Virage de Bendor`, `Courbe du Garlaban`, `Virage du Lac`, `Virage du Pont`.

## Execution

1. Freeze/source-audit the session (no `lap_number` filtering; segment scan),
   record before-hashes, then run the guarded exporter and the folder validator.
2. Read `TESTING_LESSONS.md`; add the failing ELMS reference/model/outline/
   resolver/TinyPedal tests **first** and register them in the `track-outline`
   feature suite.
3. Detect corners in scratch, review them against the real signals, then curate
   every official bend (including the two flat WOT bends and the Chicane Nord
   pair the brake detector merges/splits wrongly) through a guarded one-shot
   initializer, following `create_paul_ricard_1a_assets.py`.
4. Bake turn anchors, generate the outline + static module, rebuild the bundle,
   export the TinyPedal labels.
5. Validate references, `--print-facts`, feature suite, full `--pw` suite,
   build currency, scope audit; write `handoff.md` / `learnings.md`, mark the
   PLAN row, commit directly on `main`.

## Boundaries

- No changes to the Paul Ricard 1A / 1A-V2-Short / 3A assets or any other
  track's reference, model, outline or TinyPedal labels.
- No raw `lap_number` filtering, no hand-copied reference, no snapshot merging.
- No original-recording cleanup; no `coach-race.log` inspection.
- Do not invent corners the lap does not have, and do not delete official names
  or flat markers to make a test easier.
