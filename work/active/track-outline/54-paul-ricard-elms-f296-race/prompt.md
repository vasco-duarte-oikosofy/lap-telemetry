# Slice 54 — Paul Ricard - ELMS / Ferrari 296 GT3: race session, faster lap?

Status: ✅ Complete — reference 2:07.601 -> 2:06.440, 6 corners refreshed, curation intact, outline + labels re-baked (`e213c76`)
Trigger: *"pick up the F296/paul ricard race session and take the coaching model
and reference lap if a faster lap exists"*

## Session in scope

`sessions/session_20261114T112528Z_paul-ricard---elms_lmu_race.parquet`
(2026-11-14, race, LMU, `Vista AF Corse 2026 #21:LM` → `ferrari-296-gt3`).
**Finalized** (`in_progress: false`, `ended_utc` set, single parquet) — no shard
freeze needed, unlike slices 41/42/49/52.

| | Value |
|---|---|
| Recorded laps | 16 (laps 1–14 valid and complete) |
| Race best | **2:06.440** (lap 10) |
| Current reference | **2:07.601** (slice 50, practice lap 8 of 2026-11-10) |
| Faster? | **yes, by 1.161 s** |

## Goal

Pipeline B (guarded update) for a combo that already has curated assets:
refresh the reference to the race's fastest clean lap and re-sync the 16-zone
model's geometry from it, preserving every curated field.

1. Guarded export through `update_reference_and_coaching_model.py` (it delegates
   the export, so the single-change audit applies).
2. Prove the curation survives: 16 official names/IDs, apex sides,
   `apex_side_source`, and the two `target_throttle_pct: 100` flat bends
   (`mistral`, `garlaban`) byte-identical.
3. The two flat bends have no braking event on any lap, so they can only be
   **preserved**, never matched — run the updater without `--preserve-geometry`
   first to show the guard firing, then with it.
4. Validate references, `--print-facts` against a known slower race lap, and the
   outline contract.

## Boundaries

- One (track, vehicle) combo. No other reference, model, outline, TinyPedal
  label or web asset may change.
- No `lap_number` filtering — segment scan only.
- **No outline re-bake.** The outline baker selects alphabetically-first among
  models with curated names; `paul-ricard---elms` has a single car model, so a
  refreshed model would move the baked anchors. That is a separate decision:
  check what the baker reports and record it, but do not push map labels around
  in this slice unless the contract test demands it.
- `trail_brake_depth_m` (bug 36) untouched.

## Required end state

1. `bash scripts/test-summary.sh --feature track-outline` and `--feature
   session-debrief` green; full `--pw` suite green.
2. `npm run build` succeeds; `dist/compare.html` current.
3. `handoff.md` + `learnings.md`; PLAN.md row updated with the commit.
