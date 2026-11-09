# Handoff — Slice 49 (Imola / F296: today's quali + race)

## Result

The race (2026-11-09 17:24Z) produced the fastest Imola lap in a 296 GT3 so far,
so the reference and the coaching geometry were refreshed. Nothing else changed.

| | Before | After |
|---|---|---|
| Reference | `…_vista-af-corse-2026-21-lm_time_01.45.534.parquet` (2026-11-07 practice) | `…_time_01.45.099.parquet` (**lap 14 of the 2026-11-09 race**) |
| Improvement | — | **0.435 s** |
| Model | 11 corners | same 11 corners; **7 triples refreshed**, 4 zones preserved verbatim |
| Outline | — | **byte-identical** (`3cd0a2e9…`, same as `artifacts/before-hashes.json`) |

Reference parquet: 5231 rows, segment-sliced lap 14, exported by
`export_fastest_reference_laps.py` under the updater; its audit reported
`1 reference lap changed … OK`, i.e. one add + one supersede and nothing else.

## The two candidate laps

| Session (2026-11-09) | Fastest clean lap | Notes |
|---|---|---|
| 17:12 quali | **1:45.186** (lap 5) | 5 clean laps, all valid |
| 17:24 race | **1:45.099** (lap 14) | lap 15 = 1:45.104; 14 clean laps |

Both are faster than the old 1:45.534, so the choice of the *fastest* was not a
matter of preference. The updater was given **both** sessions in one run, so the
exporter scanned all 21 complete laps itself and picked lap 14.

## Corner geometry (was → now)

| Corner | Entry | Apex | Exit |
|---|---|---|---|
| t1 Tamburello *(preserved)* | 513 | 699 | 710 |
| t2 Variante Villeneuve 1 | 1229→1227 | 1427→**1411** | 1433→1419 |
| t3 Variante Villeneuve 2 *(preserved)* | 1404 | 1417 | 1420 |
| t4 Tosa | 1604→1601 | 1705→1717 | 1727→1735 |
| t5 Piratella | 2200→2209 | 2325→**2340** | 2351→2354 |
| t6 Acque Minerali 1 | 2638→2658 | 2847→**2861** | 2854→2864 |
| t7 Acque Minerali 2 *(preserved)* | 2836 | 2858 | 2861 |
| t8 Variante Alta 1 | 3235→3245 | 3389→3390 | 3396 |
| t9 Variante Alta 2 *(preserved)* | 3374 | 3396 | 3398 |
| t10 Rivazza 1 | 3996→3990 | 4122→**4131** | 4141→4143 |
| t11 Rivazza 2 | 4201→4203 | 4262→4266 | 4298→**4271** |

Largest move: 20 m (Acque 1 entry). Guard was `--max-geometry-delta-m 40`.

## What was preserved, and why (the "flat turns" instruction)

This model carries **no `target_throttle_pct: 100` flat markers** (Imola's
curated corners are nine real braking corners plus two chicane second halves),
so "keep the flat turns" translates to: keep the hand-reviewed zones the
detector cannot refresh. Four corners were frozen with `--preserve-geometry`
and survived byte-identical:

- **t1 Tamburello** — the exit boundary is *throttle modulation*, not a corner
  edge. Across the 21 clean laps of these two sessions the detected exit lands
  anywhere in **704–780 m**, and four laps produce a second spurious "corner" at
  735–794 m where the driver reapplies throttle. Entry is noisy too (423–549 m).
- **t3 Villeneuve 2, t7 Acque 2, t9 Alta 2** — each chicane is **one** braking
  event to the detector: it always reports a single event at ~1405–1446 m
  (Villeneuve), ~2830–2861 m (Acque), ~3361–3395 m (Alta). The first half claims
  it; the second half has no event of its own on any lap, ever.

Without `--preserve-geometry`, the matcher flipped ownership this time: `t3`,
`t7` and `t9` (3–10 m from the event apex) won the events nearest-first and the
**first** halves `t2`, `t6`, `t8` were reported unmatched — the mirror image of
bug 29, and it would have left Villeneuve 1 / Acque 1 / Alta 1 stuck on
Ginetta-era geometry while their neighbours moved onto the same apex.
Full evidence: `artifacts/signal-review.txt` (per-lap events + per-corner
brake/throttle/speed for all 21 laps).

Every name, id, short name, apex side and `apex_side_source` is identical to
`artifacts/model-before.json` (`artifacts/curation-check.txt`).

## Source handling — read this before re-running anything

The race recording was **never finalized**: the sidecar still says
`in_progress: true`, `ended_utc: null`, there is no canonical `.parquet`, and the
recorder appended a new `partN` while this slice was running (93 shards at the
first scan, 94 during the freeze).

- `artifacts/freeze_source.py` concatenated the **closed** `partN` shards
  (everything below the highest) in numeric order and collapsed 7535
  exact-duplicate consecutive rows (112 144 → 104 609). The 17 overlapping
  `snapN` snapshots and the highest shard were excluded.
- The frozen copy lives in git-ignored `var/tmp/imola-f296-quali-race/` under the
  canonical session basename plus a sidecar, so the export script's track-slug
  parser and the reference validator's provenance scan both resolve it.
- Hashes of all 93 shards + the frozen file: `artifacts/source-manifest.json`.
- **If the session is ever finalized, re-run the guard.** The frozen file is a
  slice of the closed shards and the exported reference is byte-equal to it, so
  the current reference stays *correct* — but a faster lap could exist in the
  tail that was still being written.

## Verified

- `artifacts/scope-audit.json`: 93/93 source shards unchanged, frozen file
  unchanged, exported ref == selected segment, **195 other curated assets
  unchanged**. Only the model + diagnostics changed, plus the ref add/delete.
- `artifacts/reference-validation.txt`: **35 references, 0 failures**; the new
  ref traces to `session_20261109T172456Z_…_race.parquet` (the frozen copy).
- `artifacts/lap15-facts.txt`: lap 15 (1:45.104) vs the new reference reports
  `lap_time_delta_s 0.005` exactly; corner names resolve (`Villeneuve 2`,
  `Acque 2`, `Rivazza 2`).
- Feature suite `--feature track-outline`: 960 assertions / 25 scripts.
  Full `--pw` suite: **2037 assertions / 80 scripts**.
- `npm run build` succeeded; `dist/compare.html` rebuilt with no content change.
- Outline untouched: re-baking produces **identical anchors** (`xy_delta 0.00`
  for all 11 turns) and the only `--check` difference is the pre-existing
  `short_name` gap on Rivazza 1/2 — see "deferred" below.

## Not done / deferred

- **1:45.099 is still the fastest known Imola lap, not a settled limit** — four
  race laps were under 1:45.5. Re-running the same command with any later
  session is the entire procedure.
- **The Imola outline is baked from the *Ginetta* model, not the F296 one**
  (`bake_outline_turns.py` picks the alphabetically-first model when all have
  11 named corners). Geometrically irrelevant today (anchors agree), but the
  `--check` reports `STALE` because the outline has `short_name: null` for
  Rivazza 1/2 while the model has short names. Fixing the selection rule and
  re-baking is a separate slice; do **not** casually re-bake — it would push
  map labels around on a track whose visual QA predates this work.
- `t2`/`t3` overlap by construction (Villeneuve 1 apex 1411 now sits *before*
  Villeneuve 2's preserved 1417). That is inherited from the Ginetta seed and is
  visible in the coach output (`Villeneuve 2` reported with an apex of 1411).
  Re-curating the chicane halves is a curation job, not a reference refresh.
- TinyPedal labels for Imola still not exported (needs the sibling map); slice
  33 (Imola ELMS alias) remains open.
