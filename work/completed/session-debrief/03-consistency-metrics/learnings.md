# Learnings — Slice 03: consistency metrics

- **Sector channels cannot support a per-lap optimal lap.** `last_sector_1_s` /
  `last_sector_2_s` are absent for whole laps (7 of 19 at Paul Ricard) and repeat
  identical values across consecutive laps to the millisecond (COTA laps 4–6),
  and the boundary update never arrives for 17 of 19 laps. "Sum of best sectors"
  would silently be computed from a handful of laps. The speed envelope
  replaces it: fastest observed speed per 1 m bin, integrated as `Σ ds / v`,
  using every clean lap and no sector channel at all.
- **The envelope has to integrate speed, not time.** The first attempt summed
  the best per-bin *time* deltas and returned 0 s, because at 200 km/h a 1 m bin
  is 0.018 s while the sim clock ticks every 0.02 s — adjacent bins frequently
  fall inside one tick, so *some* lap always wins a bin with a delta of zero.
  Integrating `ds / v_max` has no such quantization trap.
- **A "clean" lap can still have a broken trace.** Paul Ricard segment 2 has a
  perfectly good duration (1:19.882, within 5% of the best) and 6235 rows over
  an 80 s clock span — 1.56× rows. The extra rows sit at the end with a stalled
  clock over the final 243 m, so the delta-t trace collapses and the corner
  reports a **3.5 s gain** on a lap that is 2.7 s slower than the reference.
  Duration-based cleanliness cannot see this; a row-rate gate can.
- **The row-rate gate is razor sharp on real data.** Across 315 eligible laps,
  `frames / (clock_span × rate)` is 1.000 ± 0.002 for 312 of them and 1.14, 1.38,
  1.56 for the three broken ones. A ±10% gate rejects exactly those three and
  nothing else. This supersedes the earlier "2× frame/duration is fine" note from
  slice 01: that factor was chosen when the 1.56× lap was assumed good, and the
  facts prove it is not.
- **Derive the sample rate per segment, not per file.** `(rows-1)/(last-first)`
  over a whole session is dragged to 43 Hz by one stalled or duplicated segment,
  which then flags every honest lap. The median of the per-segment rates is
  stable (50.0 Hz everywhere in `dev/sessions`).
- **The traffic lap was poisoning the rankings, not just the pace summary.**
  `lap_pace` filtered to clean laps but `recurring_losses`, `inconsistent_corners`
  and `phase_spread` did not, so one 1:30 lap created an 11 s "inconsistency" at
  corner 2. Filtering once, in `build_consistency`, is the only safe place.
- **Two rankings, two meanings.** `recurring_losses` is a mean and says "slow
  here every lap"; `inconsistent_corners` is a spread and says "erratic here".
  Ranking the second in seconds rather than km/h changes the order: the Paul
  Ricard hairpin has a 39 km/h spread but a tiny time spread, while the fast
  sweeper's 6 km/h spread costs real time.
- **`laps_affected` is out of the laps measured, not out of all laps.** Pont's
  exit phases are measured on 4 laps, all affected. The report must say "all
  four laps where it was measurable", not "all sixteen".
