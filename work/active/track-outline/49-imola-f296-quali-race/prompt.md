# Slice 49 — Imola / Ferrari 296 GT3: check today's quali + race for a faster lap

Status: ✅ Complete — reference 1:45.534 → 1:45.099, model refreshed, curation intact
Trigger: *"pick up the latest F296/imola sessions, quali and race, and check for a
faster than reference lap. then update the coaching model and reference laps, and
keep the flat turns and official turn names"*

## Sessions in scope

| Session (2026-11-09) | File | Fastest complete lap |
|---|---|---|
| 17:12 quali | `sessions/session_20261109T171239Z_autodromo-enzo-e-dino-ferrari_lmu_quali.parquet` | 1:45.186 (lap 5) |
| 17:24 race | `sessions/session_20261109T172456Z_…_race` (unfinalized, `partN` shards) | 1:45.099 (lap 14) |

Vehicle in both: `Vista AF Corse 2026 #21:LM` → canonical `ferrari-296-gt3`.
Current reference: **1:45.534** (`session_20261107T125508Z` practice, slice 44).

## Goal

Replace the reference with the fastest lap if (and only if) it is genuinely
faster, and refresh the `(autodromo-enzo-e-dino-ferrari, ferrari-296-gt3)`
coaching-model geometry from it — preserving **every** curated field: official
turn names, IDs, short names, apex sides, and the flat/compound corner markers
(`t1 Tamburello` noise zone, `t3`/`t7`/`t9` compound second halves).

## Boundaries

- One (track, vehicle) combo; no other track's reference, model or outline may change.
- No `lap_number` filtering — segment-based analysis only.
- The race recording is unfinalized: freeze the closed `partN` shards read-only
  and record their hashes (slice 41/42 procedure), never read the live shards
  mid-run.
- Every curated turn name, ID, short name, apex side and flat marker survives;
  anything the new lap cannot reproduce is preserved and justified from the
  signals of *all* clean laps, not one.
- `product/data/track-outlines/autodromo-enzo-e-dino-ferrari.json` is per-layout:
  re-baked turn anchors are allowed to follow the model, nothing else may change.

## Required end state

1. `bash scripts/test-summary.sh --feature track-outline` green; full `--pw` suite green.
2. `npm run build` succeeds and `dist/compare.html` is current.
3. `handoff.md` + `learnings.md` in this folder; PLAN.md row marked ✅ with the commit.
