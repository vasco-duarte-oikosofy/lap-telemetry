# Slice 53 — Silverstone National / Ferrari 296 GT3: coach debrief on the quali and the race

Status: ✅ Complete — both debriefs run against the live assets; see handoff.md
Trigger: *"run the coach debrief on the latest F296/Silverstone national combo.
Use both the race, and the quali sessions"*

## Context

Slice 52 shipped the first `(silverstone-national-circuit, ferrari-296-gt3)`
reference (0:54.295) and coaching model. This slice is the acceptance run: does
the new model actually coach the driver on the sessions it was derived from?

## Sessions in scope

| Session | Source | Laps |
|---|---|---|
| 06:52 quali | `sessions/session_20261114T065241Z_silverstone-national-circuit_lmu_quali.parquet` (finalized) | 12 recorded |
| 07:04 race | frozen closed-shard copy in `var/tmp/silverstone-national-f296-quali-race/` (slice 52) — the live recording is still unfinalized | 34 recorded |

Reference and model resolve **by (track, car)** — nothing is passed by path, so
this also proves bug-27 resolution for the new combo in the product path.

## Goal

Run `lap-telemetry debrief` end to end on both sessions and record what the
coach says:

1. `--json` facts + `--report-only --no-llm` Markdown report per session.
2. One scripted coaching conversation per session (the interactive REPL driven
   from an inputs file, exactly as slice 51 did): a why-question about a named
   corner, `/corner <flat bend>`, `/laps`, `/plan`, `/quit`.
3. A short read of the result: do the priorities name real corners, is the
   optimal lap plausible, does the flat-bend corner explain itself, and do the
   two sessions agree on the same weakness?

## Boundaries

- Analysis only. **No** reference, model, outline, web asset or bundle changes:
  if the run reveals a data problem, record it as a finding for a later slice,
  do not fix it here.
- Nothing from `sessions/` is modified; the race is read from the frozen copy.
- `coach-race.log` stays untouched.

## Required end state

1. `bash scripts/test-summary.sh --feature session-debrief` and
   `--feature track-outline` green (`--pw` before the final commit).
2. `npm run build` succeeds and `dist/compare.html` is unchanged.
3. `handoff.md` + `learnings.md` in this folder; PLAN.md row marked ✅ with the commit.
