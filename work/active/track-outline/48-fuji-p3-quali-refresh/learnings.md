# Learnings — Slice 48 (watching the fix do its job on real data)

- **The fix shows up as a *different warning*, not as a cleaner run.** After
  nearest-first matching the Fuji refresh still aborts without
  `--allow-unmatched`, but on `13th Corner, Netz` instead of `13th Corner, Netz
  Hairpin`. A guard whose message changes to the truth is the cheapest proof
  that the internals changed for the better — worth deliberately running the
  same command pre/post fix and diffing its output.

- **A live validation needs the marker's numbers, not just "it worked".** Netz
  came out of the refresh at exactly 3284/3310/3310, the same tuple it went in
  with, while the hairpin moved to its own event at 3385. That symmetry — one
  corner frozen, its neighbour refreshed — is what distinguishes a correct
  match from a lucky one.

- **`--allow-unmatched` is the honest flag for marker corners.** They have no
  braking event by definition, so their "unmatched" status is expected, not a
  failure to investigate. The run now prints exactly two such warnings for Fuji,
  both legitimate.

- **A geometry-delta guard can be chosen to encode the fix's contract.** Using
  `--max-geometry-delta-m 50` here admitted 100R's known +45 m noise move while
  still aborting the bug-29 steal (+129 m). The threshold is a statement about
  which moves you are willing to believe.

- **Re-baking is not optional when the model moves.** `test_outline_turns.js`
  pins Fuji's 11 anchors to the model, and the TinyPedal labels are derived from
  those anchors — so a model refresh necessarily propagates to the outline,
  the static module, the bundle and the shipped `turns.json`. Skipping any of
  them leaves the repo in a state its own contract rejects.

- **Validator provenance is a heuristic, and tolerances make it ambiguous.** The
  new 1:36.544 reference was reported as coming from the 2026-10-25 race, which
  has a 1:36.564 lap inside `TIME_TOL_S`. Proving the real source took a
  row-for-row comparison against today's session slice (4760 rows, identical
  bar schema metadata). "first match within tolerance" is not provenance;
  "closest match" would be.

- **20 ms is still 20 ms.** Slice 46 argued the refresh was not worth it; doing
  it anyway was justified by the *validation* goal, not by the time gained. The
  handoff says so explicitly, so the next reader does not mistake this for a
  reversal of the earlier judgement.
