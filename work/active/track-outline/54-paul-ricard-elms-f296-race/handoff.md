# Handoff — Slice 54: Paul Ricard - ELMS / F296, race session (faster lap found)

## Result

| | Before | After |
|---|---|---|
| Reference | `…_time_02.07.601.parquet` (2026-11-10 practice lap 8) | `…_time_02.06.440.parquet` (**2026-11-14 race lap 10**) |
| Improvement | — | **1.161 s** |
| Model | 16 zones | same 16; **6 refreshed**, 10 preserved verbatim |
| Outline | 16 anchors on the old apices | re-baked, **6 anchors moved** (≤33 m), 362 lines |
| TinyPedal labels | — | re-exported, 6 `s_frac` values changed |

Source: `sessions/session_20261114T112528Z_paul-ricard---elms_lmu_race.parquet`
— **finalized** (`in_progress: false`, `ended_utc` set, single parquet), so no
shard freeze was needed.

Commits: this one (data + tests + docs). Nothing else changed.

## The lap

14 complete laps; the export chose race lap 10 at **126.440 s** by authoritative
timing, 6297 rows. Second best in the session was 2:06.561 (lap 11) — the whole
race lived in the 2:06.4–2:07.4 band.

## Corner geometry (was → now)

Only the corners whose detected event did **not** swallow a neighbour moved:

| Corner | Entry | Apex | Exit | Note |
|---|---|---|---|---|
| S de la Verrerie 1 | 484→481 | 621→**623** | 690→**651** | shorter exit |
| S de la Verrerie 2 | 699→**711** | 739→**747** | 790→**766** | |
| Virage de la Sainte-Baume | 1610→**1597** | 1663→**1661** | 1690→**1663** | |
| Chicane Nord 1 | 2805→**2787** | 2960→**2962** | 2992→**2965** | |
| Chicane Nord 2 | 2994→**2970** | 3044→**3048** | 3072→**3063** | |
| Courbe de Signes | 3780→**3776** | 3954→**3948** | 3995→**3950** | exit −45 m (hand-extended before) |

Preserved (10): `hotel_1`, `hotel_2`, `camp`, `mistral`, `beausset_1`,
`beausset_2`, `bendor`, `garlaban`, `lac`, `pont`. Every name, id, apex side,
`apex_side_source` and both flat markers are byte-identical
(`artifacts/curation-check.txt`).

## Why 10 corners were preserved — three different reasons

The faster lap's detector produced only **10 events for 16 corners**, and three
of them are long spans that cover a **neighbour**:

1. **Chained corners collapse** — `hotel_1`+`hotel_2`+`camp` come out as one
   event (1184→1539, apex 1507), `beausset_1`+`beausset_2` as one (4178→4512,
   apex 4379), `lac`+`pont` as one (5182→5492, apex 5473). The nearest-first
   matcher gives each merged event to the nearest apex (`camp`, `beausset_1`,
   `pont`), leaving the other halves unmatched. Adopting the merged spans would
   have stretched `camp`'s entry back **278 m** into the Hôtel and `pont`'s entry
   **233 m** into the Lac — the `--max-geometry-delta-m 40` run flagged exactly
   that (`artifacts/dry-run-delta-guard.txt`). So the whole cluster is kept:
   `hotel_1/2`, `camp`, `beausset_1/2`, `lac`, `pont`.
2. **Flat bends** — `mistral` (1815–1920) and `garlaban` (4900–5170) have no
   braking event at all. Verified on *this* lap: min throttle **1.00**, max
   brake **0.00** across both spans, identical to the old reference
   (`artifacts/flat-bend-check.txt`).
3. **Bendor — a judgement call, stated plainly.** The detector's apex is 22 m
   earlier (4809 vs 4831) and its exit 48 m shorter (4847 vs 4895), which the
   default 40 m guard flags. Adopting it also cost a readable map label: at the
   densest overlay size (400 px, 0°) the widget went from 15 named labels to 14
   (Bendor fell back to `T13`), failing TinyPedal's own "at most one
   number-only fallback" gate. A 22 m apex change is within lap-to-lap wander
   and buys nothing measurable, so the slice-50 reviewed geometry stays.

## Outline and labels (downstream of the model, so they had to move)

`paul-ricard---elms` has exactly one car model, so the refreshed model *is* the
baker's source: the outline went `STALE` and had to be re-baked.

- `artifacts/rebake_outline.py` re-bakes **in place with the compact writer**
  (362 lines; `bake_outline_turns.py` alone would have written ~6000 and blown
  the 437-line ceiling), keeps the map-only `Ste-Baume` alias, and re-points
  `alignment.reference_lap`/`notes` at the new reference.
- `bake_outline_turns.py --check` still prints `STALE`, because a *fresh* bake
  writes `short_name: "Sainte-Baume"` while the outline carries the map alias
  `Ste-Baume`. That difference predates this slice (verified by checking the
  committed pair before the change) and is the same class of alias drift slice
  43 documented at Imola.
- Static module regenerated (`generate_outline_module.js`) and the bundle
  rebuilt; TinyPedal `Paul Ricard - ELMS.turns.json` re-exported (6 changed
  `s_frac`s), `--check` clean, and the sibling widget test is green again.

## Verified

- `artifacts/reference-validation.txt`: **38 references, 0 failures**; the new
  reference traces to the race session.
- `artifacts/lap3-facts.json`: race lap 3 (2:07.481) reports
  `lap_time_delta_s 1.041` (= 127.481 − 126.440) and names resolve
  (`Hôtel 1 entry 0.283 s`, `Camp minimum_speed 0.25`, `Bendor entry 0.219`).
- `--feature track-outline`: **1335 assertions / 31 scripts — ALL PASS**.
- Full `--pw` suite: **2862 assertions / 98 scripts — ALL PASS**.
- `npm run build` succeeded; `dist/compare.html` rebuilt (outline data changed,
  so this one is expected).
- Test pins moved to the new reality: `test_paul_ricard_elms.py` now expects
  lap 10 / 6297 rows / 126.440 s.

## Deferred / notes for the next agent

- **Bendor will be re-tempted at every future refresh** (its event apex sits
  22 m early on every session checked so far). Preserve it by ID or accept the
  label regression deliberately — but note the label gate in the sibling repo
  is the thing that will fail.
- The `--check` `STALE` for this track is alias-only; do not "fix" it by
  re-baking without the compact writer and the `Ste-Baume` alias, or you will
  produce a 6000-line outline and lose the map alias.
- `visual_qa.status` remains `pending` (automated render only).
- The race is a good debrief candidate (`lap-telemetry debrief`) if you want the
  corner priorities from 14 clean laps — not run in this slice.
