# Learnings — Slice 12: coach speaks curated short corner names

- **The value was already there and already curated.** `short_name` lives in
  `product/data/track-coaching/monza-curva-grande-circuit_*.json` (6 of 10
  corners) and `docs/specs/MAP_TURN_NAMES.md` documents it — the only reason the
  coach said "Variante della Roggia 2" is that `Corner` is a plain dataclass with
  an explicit field list and `validate_corner()` builds it key by key, silently
  dropping anything it does not name. Same trap as bug 11 (schema drift): when a
  dataclass mirrors a JSON schema, an unknown key disappears without a warning.
- **One property, two call sites.** Every spoken name flows through
  `CornerLoss.corner_name` (facts → template/LLM) or `CornerExited.corner_name`
  (corner-exit prompt). There is no third path — the map/turn-label code builds
  its own name from the *outline* JSON, not from the coaching model, so nothing
  in `web/` needed touching.
- **`Corner` is mutable**, which made a cheap test possible: load the real
  Barcelona model, assign `short_name = "S<n>"` to every corner in memory, run
  `compare_laps()` against the tracked fixture and assert every fact carries the
  short name. No new parquet, no session dependency, 30 facts covered.
- **Beware `top_n` when asserting on a specific corner.** My first version
  curated `t1` only and asserted "t1 produced facts" — it failed because t1 is
  not in Barcelona's top 20 losses/gains for that fixture. Asserting an invariant
  over *all* returned facts (every fact uses its own corner's short name) is both
  stronger and independent of which corners happen to be fast or slow.
- **Empty string is a real hazard** for TTS: `"short_name": ""` would produce
  "You lost two tenths at the apex of ." — `validate_corner()` now normalises
  blank/whitespace-only values to `None` and rejects non-strings. The blank case
  is pinned by a test.
- **Name vs identity:** `corner_id` (`t3`) is what filters, caches and model
  lookups use; `name` is the official long name kept for reference/traceability;
  `short_name` is only what the driver hears. Do not collapse them.
