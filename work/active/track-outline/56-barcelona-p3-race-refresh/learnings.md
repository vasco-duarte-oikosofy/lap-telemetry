# Learnings — Slice 56 (Barcelona / P3 race refresh, superseded)

## A slice's data outcome can be superseded before it is committed

The previous agent produced a correct refresh (1:36.456 → 1:36.319 from race
lap 16) and never committed it. Before the next agent got there, slice 57
exported a **faster qualifying lap (1:36.040)** for the same combo: the guarded
exporter deleted the 1.36.319 file and wrote its own model. `git status
product/` was therefore clean, and every artifact in this folder looked like
"work that should be on disk" when in fact nothing was.

**Rule for the next agent:** before writing a handoff that claims "reference
moved from A to B", run `git log -1 -- <reference path>` and
`ls product/data/reference-laps | grep <combo>`. If the claimed file is absent
from the working tree *and* never appeared in a commit, the right closure is a
documented supersession, not a re-export.

## The 40 m guard's flags are mostly merged events, not real motion

On race lap 16 the detector produced **10 events for 12 corners**, and 8 of the
12 corners were flagged >40 m. The flagged deltas were almost all *entry*
inflation (Turn 1 −159 m, Turn 10 −157 m, Turn 4 −130 m, Turn 12 −108 m,
Turn 14 −107 m): the braking event for the corner began inside the previous
corner, so the matched span's boundary is its neighbour's boundary.

`artifacts/controls-review.json` is the cheap way to tell the two cases apart —
it prints, per corner, curated vs detected **geometry plus window row count,
min speed, min throttle, max brake and mean apex steering**. A span that starts
150 m early shows a much larger row count and a throttle/brake profile that
belongs to the corner before it.

Outcome here: 11 corners preserved, and the only accepted change was
**Turn 3 — Renault** (entry 1068 → 1081, apex 1161 → 1163, exit 1163 → 1167 —
inside the guard, so it never even needed review). Two corners (Turn 2, Turn 8)
had *no* detected event at all and were preserved automatically.

## Freezing an in-progress race is a hash-stability exercise

The sidecar was `in_progress: true` with **no canonical parquet**, only
`part0..part95`. `artifacts/freeze_source.py` concatenates the numerically
ordered parts *excluding the highest* (the one being written), and re-checks the
part hashes during the read so a rolling part is caught rather than silently
mixed. The merged file keeps the canonical session basename so the updater's
vehicle/track inference works unchanged, and lands in gitignored
`var/tmp/<slice>/` so the shards themselves stay untouched.

## Recorded evidence rots — re-record it at closure

`artifacts/feature-track-outline.txt` and `artifacts/feature-session-debrief.txt`
were left by the previous agent mid-flight and captured **14 failing
assertions** (`test_delta_time_gains`, `test_js_pipeline_contract`,
`test_generate_track_coaching_model_from_reference`) that described a
half-applied state. Nothing was wrong with the code: slice 57's commit brought
the pins back in line. Both files were re-run and overwritten at closure, and
`reference-validation.txt` — which was **empty** — was regenerated.

**Lesson:** a stale artifact is worse than a missing one, because the next agent
starts by "fixing" tests that already pass.

## Two suites that hide a full-suite failure

`--feature track-outline` (36 scripts) and `--feature session-debrief`
(25 scripts) were both green while the full `--pw` run failed on
`dev/scripts/test_repo_reorg_root_cleanup.js`, a repo-root guard that asserts the
set of *tracked top-level directories*. Remote commit `15dc971` added a tracked
`.agents/` tree, which the allowlist does not know. Feature suites structurally
cannot see repo-root guards — that is what the milestone `--pw` run is for.

## Small mechanics

- The build output is `product/dist/compare.html` (not a root `dist/`), and an
  unchanged bundle leaves `git status` clean — good evidence no data reached the
  UI bundle.
- `dev/scripts/validate_reference_laps.py` prints `38 reference laps checked, 0
  failures`; the superseded reference is *deleted* by the guarded exporter, so
  that count does not grow when a refresh replaces a file.
- `python -m lap_telemetry summary <parquet>` is the fastest way to produce
  authoritative per-lap evidence, including the partial tail lap (`lap 20,
  0:37.850`) whose `-` sectors show it is not a complete lap.
