# Learnings — Slice 50 (Paul Ricard - ELMS / Ferrari 296 GT3)

- **The sim names a layout by what it is, not by what the model assumed.**
  `Paul Ricard - ELMS` is a *different* configuration from 1A, and the only
  cheap way to prove which one it is: compare the new lap's racing line against
  the curated 1A reference line. It leaves the 1A path in exactly two places
  (max 75 m and 67 m), which are the tight Verrerie `S` and the **Chicane Nord**
  pair in the middle of the Mistral. Everything else is within 4 m. That single
  measurement identified the layout (LMU's 5.8 km 1C/ELMS config) before any
  asset existed, and it also proves the outline must not alias 1A.
- **A brake/throttle detector cannot see a compound double-right whose speed
  minimum is only 7 kph below its own mid-corner plateau.** The Beausset here
  was reported as *no corner at all*: the brake event and the coasting lift merge
  into one zone whose `prominence` (local ±80-sample) is 7.4 kph, below the 10 kph
  brake-zone threshold — even though the entry was 227 kph. The 1A lap had the
  same corner as a detected event because the P3 carried more speed mid-corner.
  Curate the double-right from the steering plateau (first apex) plus the second
  speed minimum, and never read "11 detected events" as "11 corners": two flat
  WOT bends are invisible too, and Hôtel/Camp/Lac split differently per car.
- **"Paul Ricard - ELMS" is not `1A` + a chicane.** The Verrerie is a real
  braking chicane here (0.74 brake, 113 kph), not the flat 1A esses, so only the
  Mistral entry bend and Garlaban stay `target_throttle_pct: 100`. Keeping the
  flat markers that exist and dropping the ones the geometry does not have is the
  correct reading of "keep the flat corners".
- **Chicane naming is genuinely ambiguous, so prefer the sources that describe
  *this* configuration.** The FIA turn-location plan reserves T8 `Chicane Sud`,
  T9 `Chicane Montréal` and T9b `Chicane Nord` for the different Mistral chicane
  options; the circuit's own 1C guide and the LMU track guide both call the pair
  the ELMS config uses **Chicane Nord** (1ère/2ème partie). Model names are
  `Chicane Nord 1/2`, spoken/map aliases `Chicane 1/2`.
- **A recorded TinyPedal map can start past the timing line, and that silently
  shifts every turn label.** The packaged ELMS map began 165 m after the
  simulator's start/finish: TinyPedal draws its start line at polyline index 0
  and anchors labels by arc length from that point, so all 16 labels landed
  ~175 m late *and* started colliding (3 of them degraded to number-only at
  600 px). Proof it is the map, not our axis: the sim's `scoring_time_into_lap_s`
  clock wraps on exactly the same frame as `lap_distance_m`, and every other
  shipped map measures within 22 m of the timing line while this one measured
  164.6 m. `dev/scripts/align_tinypedal_map_start_line.py` rotates `map`+`dist`
  and the `desc` sector indices, re-zeroes the distance axis and refuses to write
  unless every outline turn anchor verifies (< 25 m). After the rotation all 16
  names fit at 400/600 px × 0/90° with zero overlaps.
- **Track maps are gitignored user data.** `tinypedal/trackmap/` is excluded from
  the TinyPedal repo, so the map rotation is a local fix that cannot be shipped;
  the packaged `.turns.json` stays canonical (`s_frac = apex / lap_length_m`) so
  it is correct for any map recorded at the timing line. Do not bake the offset
  into `s_frac` — that would break every other machine and the documented
  contract.
- **Two pre-existing map anomalies are worth a bug, not a silencer.** The sweep
  found `Silverstone Grand Prix Circuit - ELMS` measuring a 2696 m axis offset
  (its rotation fails anchor verification at 1510 m) and
  `Autódromo José Carlos Pace` at 34.7 m (legacy outline with no `lap_length_m`,
  so its axis is the geometric centreline). Both are outside this slice; the tool
  refuses them loudly instead of rotating.
- **The filename fallback flattens runs of dashes.** `session_…_paul-ricard---elms_lmu_practice.parquet`
  infers `Paul Ricard   Elms`, which slugs to `paul-ricard-elms`, while the sim
  name slugs to `paul-ricard---elms`. The manifest needs both keys — same trap as
  1A. The outline keeps both in `accepted_sim_track_names` so
  `register_outline.py` adds both.
