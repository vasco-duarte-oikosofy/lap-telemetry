# Learnings — Slice 13

- A generic word-stripper was unsafe: removing Hairpin collapses Fuji's Netz
  Hairpin into Netz; removing Entry/Exit fuses Becketts' two named phases.
  Replaced the unfinished spike with reviewed aliases and conservative fallback.
- Missing aliases existed in every model, not just tracks outside Monza. Imola,
  Barcelona and Daytona already had partial curation. Reusing existing aliases
  by official name keeps vehicle models consistent without overwriting curation.
- A memory-address keyed writer cannot survive reloading JSON: freshly parsed
  corner dicts have different identities. Stable corner IDs plus stale-preview
  checks are essential; tests now verify actual persistence, not just preview.
- Single-token 100R also needed a spoken alias despite the multiword coverage
  rule, otherwise the same digit-by-digit TTS problem persists at Fuji.
- A few proper multiword names should not be shortened further: Eau Rouge,
  La Source, Les Combes and Netz Hairpin keep their identity in short_name.
- The legacy Spa model has 69 detected corners and was already 636 lines. Only
  its formatting was compacted (separate refactor commit); no attempt was made
  to correct its detection or re-export its reference in this naming slice.
- Existing map tests coupled map short labels to coaching short aliases.
  Replaced that equality with fixed map-label expectations while retaining
  official-name and apex-distance parity, so speech spelling cannot silently
  force map-label changes. Future rebakes still need separate review.
- All stock full-suite failures were the known Windows import-path issue.
  An uncommitted loader converting drive-letter specifiers to file URLs lets
  the full suite actually run. Preserve query suffixes before URL conversion:
  otherwise cache-busting `?t=...` becomes part of the filename and fails.
