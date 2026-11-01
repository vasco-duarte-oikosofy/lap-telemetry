# Slice 13 — Curate spoken names across all coaching models

**Status:** ✅ Complete in `328f1c2`; formatting-only prerequisite `bd32dbb`.
User requested the all-model pass after slice 12. See handoff/learnings/artifacts.

**Feature tests:** `bash scripts/test-summary.sh --feature coach-short-corner-names`

## Acceptance

- Review every `product/data/track-coaching/*.json` model (all cars/layouts).
- Every name with two or more words has a nonblank curated `short_name`.
- Remove unnecessary descriptors, e.g. Farm Curve → Farm. Keep recognizable
  proper names and distinctions (Eau Rouge, Netz versus Netz Hairpin,
  Becketts Entry versus Exit); do not blindly strip words.
- Preserve numbered subdivisions (Lesmo 1/2, Roggia 1/2, Ascari 1/2/3).
  Spell numbers >= 10 in spoken names: Turn 10A → Ten A, Turn 10B → Ten B,
  Turn 12 → Twelve. Digits < 10 stay digits. Preserve official `name` and IDs.
- Existing curated names win; reuse them consistently across vehicle models.
- Use a guarded, previewable data-only writer. Verify parsed models are
  identical with `short_name` removed, including reference/geometry/targets.
- No reference export, geometry regeneration, runtime algorithm changes or
  map-label changes. Map labels remain independently baked display data;
  speech-oriented number spelling must not force map rebakes.

## Execution

1. Add corpus and writer regressions, observe red through test-summary.
2. Replace the unfinished name-stripping spike with reviewed name mappings,
   narrow numbered-turn handling and a formatting-preserving guarded writer.
3. Preview, review, apply and audit. Keep every touched file <= 437 lines;
   compact the pre-existing 636-line legacy Spa model without semantic changes.
4. Update fixture-dependent tests where they assume models lack short names.
   Keep synthetic fallback coverage; do not change the coach implementation.
5. Run feature tests, full suite with --pw, and build. Record existing platform
   failures separately if present; do not fix unrelated bugs.
6. Commit on main, update PLAN status/hash, write handoff and learnings, stop.
