# Slice 43 — Imola / Ferrari 296 GT3 (new car, existing track)

Status: ✅ Complete in `24eb9a6`
Trigger: the driver ran an Imola practice session today (2026-11-07, LMU,
`session_20261107T075003Z_autodromo-enzo-e-dino-ferrari_lmu_practice.parquet`)
in the Ferrari 296 GT3 `Vista AF Corse 2026 #21:LM`. Fastest complete lap:
lap 5, 1:46.173 (106.173 s), valid.

## Goal

Give `(autodromo-enzo-e-dino-ferrari, ferrari-296-gt3)` its own reference lap,
coaching model and outline turn anchors, without losing the curated Imola
content. Imola only has assets for the Ginetta LMP3 and the Ferrari 499P; the
coach resolves by (track, canonical car), so the 296 currently resolves to
nothing.

## Execution

1. Guarded export of the fastest clean lap as the F296 reference (one combo,
   `AUDIT: 1 reference lap changed`, folder validator clean).
2. Seed the F296 coaching model from the curated Imola model
   (`autodromo-enzo-e-dino-ferrari_dkr-engineering-4-elms25.json`) — official
   turn names, IDs, apex sides, short names, and every flat marker copied
   verbatim — then refresh geometry through
   `update_reference_and_coaching_model.py --ref … --allow-unmatched`.
3. Prove the curated content survives byte-identical (names, IDs, apex sides,
   short names, `target_throttle_pct`).
4. Re-bake the outline turn anchors (repo contract: outline turns must match the
   curated model the outline was baked from) and rebuild the static module +
   standalone bundle.
5. Validate references, `--print-facts`, feature suite + full `--pw` suite,
   build, scope audit; write `handoff.md` / `learnings.md` and mark the PLAN row.

## Boundaries

- No other track's reference, model or outline may change.
- No `lap_number` filtering (segment-based analysis only).
- No edits to the recorder's live session files.
- **Every curated turn survives**: 11 official Imola names (`Tamburello`,
  `Variante Villeneuve 1/2`, `Tosa`, `Piratella`, `Acque Minerali 1/2`,
  `Variante Alta 1/2`, `Rivazza 1/2`), their IDs, apex sides and short names.
- **Every flat turn survives**: the curated models carry no
  `target_throttle_pct` markers at Imola (none of the 11 corners is flat for
  either car), so "keep the flat turns" means the GT3 lap must not delete the
  three compound second halves (`Villeneuve 2`, `Acque 2`, `Alta 2`) that a
  slower car cannot reproduce as separate braking events.
