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

---

# Review round 2 — alternating sides, small-map text

## Alternating inside/outside is what makes dense tracks work

Le Mans packs 8 of its 19 turns into sector 3. Placing every label on the
*outside* of the loop could not fit them: 18/19 with one label dropped and one
degraded to a number. Alternating the side per turn (odd = outside, even =
inside) gave **19/19 with names** and *better* adjacency (label box 3.6 px from
the apex on average, was 5.1). Across all 14 backfilled tracks, alternating is
better or equal on 13 and only slightly worse on Silverstone GP — and the
fallback below removes even that.

## Candidate order: text, then side, then nudge

The first version sorted candidates side-first, so a label would drop its name
(`T13`) before it would switch to the other side of the track. Reordering to
text -> side -> nudge fixed Silverstone GP: keeping the name matters more than
which side of the ribbon it sits on.

## A nudge needs two caps, not one

One cap of `2.4 x fontSize` gave 12 px of drift on a 120 px map — 10 % of the
map, which reads as "the label left its corner" (exactly the earlier complaint).
Splitting it fixed that:

- **along the track**: up to `2.4 x fontSize` — sliding past a neighbour still
  reads as attached;
- **along the normal**: up to `min(2.4 x fontSize, 4 % of mapSize)`.

Effect on Interlagos at 120 px: worst drift 10.8 px -> 2.8 px.

## Tightening the gap on small maps backfires

Shrinking `gap_px` from 0.75 to 0.5 x fontSize below 150 px *reduced* coverage
(12/15 instead of 13/15) and increased drift, because a label closer to the
track needs a bigger nudge to escape its neighbours. Reverted; the gap stays
0.75 x fontSize at every size.

## Text shortening is mostly curation, a little grammar

Curating `short_name` did the heavy lifting on Interlagos (`Descida do Lago 1`
-> `Lago 1`, `Curva do Sol` -> `Sol`, `Subida das Boxes` -> `Boxes`,
`Arquibancadas` -> `Arquib.`): at 250 px it went from one label dropped and two
numbered to **15/15 with names**. The only *algorithmic* shortening worth having
is dropping the `T` prefix below 150 px (`4 Lago 1`), which buys ~2 characters.
Everything else needs a human: auto-stripping produced "Grande" from "Curva
Grande".

## Final measured state

| size | result |
|---|---|
| 250 px | 14/14 tracks: every turn labelled with its name, zero overlaps |
| 150 px | 13/14 tracks complete |
| 120 px | 12/14 complete; Interlagos 15/15 (12 named + 3 numbers); Le Mans 16/19 (dense Ford chicane cluster drops) |
