# Learnings — Slice 04 (backfill)

- **Sorting beats rolling for `lap_distance_m`.** The slice-01/02 helper rolled
  the lap at the *first* decreasing sample. That is wrong for two reasons: a lap
  can start just before zero (so the wrap is not the first descent) and real
  laps contain metre-scale jitter descents. `paul-ricard---1a-v2-short` hit both
  at once: every corner collapsed onto one anchor `(72.1, -48.0)` and 12 of 13
  labels were dropped. Sorting the samples by distance (and pairing x/y through
  the same index order) is robust and simple. **Symptom to remember: identical
  anchors for every corner.**

- **Only 14 of 22 outlines can have turn labels.** The blocker is coaching-model
  curation, not the renderer: 6 track models are still `turn 1..N` placeholders
  and several are wildly over-segmented (Spa 69, Lusail 16, COTA 14, Bahrain 13,
  full Monza 6 for 11 turns). Baking those would have printed confidently wrong
  turn numbers, so the bake refuses and says why. Turn labels are only as good
  as the models behind them.

- **One track can have several models with different corner counts** (Daytona
  12 vs 6, Barcelona 16/12/14, Bahrain Outer 6/11). Ranking by curated-name
  count, then corner count, then filename picked the right one every time and
  stays deterministic; the tool warns when the top two disagree.

- **The label that is too wide is rarely the long name — it is the neighbour.**
  After shrinking type to 5.75 px, most "degraded to number" labels had short
  names all along (`Sunset Bend`, `La Bretelle`, `Rivazza 1`): they fall back
  because their apex is inside a chicane pair, where two labels cannot coexist
  within the adjacency budget. Short names only fixed the genuinely long or
  redundant ones (Barcelona `Turn 3 — Renault`, Laguna `Corkscrew (Turn 8)`,
  Monza `Curva Alboreto (Parabolica)`) — that is exactly where curation paid
  off, e.g. Barcelona went from 13/14 with one drop to 14/14.

- **`turn N` is legitimate naming on some circuits.** Road Atlanta's model uses
  "Turn 1", "Turn 4 (The Esses)"; the placeholder rule turns those into `T1` and
  `T4 Esses`. Do not "fix" them into proper names without a source.

- **A preservation guard must not fail the write.** Throwing on an unparsable
  existing outline broke `test_compute_boundaries.js`, which writes a `SENTINEL`
  file to prove `--overwrite` replaces it. A file that is not valid JSON cannot
  contain curated turns, so warn and continue — and add a regression test for
  exactly that case.
