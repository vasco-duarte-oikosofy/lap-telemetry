# Handoff — Slice 01: Architecture and Code Review

## State on disk

New mission created (read-only review — no production code changed):

```
work/active/architecture-code-review/
  PLAN.md
  01-architecture-code-review/
    prompt.md
    20260617_architecture_code_review_glm5.2.md   ← THE DELIVERABLE (findings)
    handoff.md                                     (this file)
    learnings.md
```

All other files in the repo are **untouched**. `git status` shows only the new
files under `work/active/architecture-code-review/` (plus the regenerated
`product/dist/compare.html` if a build was run — see below).

## What was done

- Read `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `work/README.md`,
  `docs/HOW_TO_START_A_NEW_FEATURE.md`.
- Walked every production module in `product/python/lap_telemetry/` (recorder + coach)
  and `product/web/js/` (non-data modules), plus `dev/scripts/compute_delta_t.mjs`.
- Measured line counts for every production file; identified the 4 hard-ceiling
  violations and the duplication clusters.
- Ran `npm run build` (✅ green, `product/dist/compare.html` refreshed) and
  `bash scripts/test-summary.sh` (fast, no `--pw`): 882 passed, 1 pre-existing failure.
- Wrote the findings to `20260617_architecture_code_review_glm5.2.md` with `file:line`
  evidence, prioritised P0 → P2, plus strengths and a follow-up-slice backlog.

## Verification performed

- `npm run build` → ✅ succeeds, `product/dist/compare.html` current (1.9 MB).
- `bash scripts/test-summary.sh` (no `--pw`) → ❌ 1 failure, **pre-existing**, unrelated
  to this review: `test_repo_reorg_root_cleanup.js` ("unexpected tracked root
  directories: .pi"). Cause: `.pi/skills/...` is git-tracked but not allow-listed or
  gitignored. This is finding **P0-1** in the review doc.
- Playwright (`--pw`) suite **intentionally not run**: this slice changes no UI or
  product code (only `work/` docs), so there is nothing for Playwright to regress.
  The fast suite was run solely to characterise current repo health for the review.

## Deferred / not done (by design — this is a read-only review)

No findings were *fixed*. Each finding in the review doc has a recommendation; the
suggested follow-up slices are listed in §6 of the findings document. The highest-
leverage next actions:

1. `repo-hygiene-fix` — resolve `.pi/` tracking so the suite is green (P0-1).
2. `refactor-template-adapter` — parameterise gain/loss × phase table; collapses the
   652-line file under the 437 ceiling (P0-2 + P2-11).
3. `refactor-connect-frame-builder` — shared `_build_frame`; `connect.py` under 437
   + a Frame↔schema↔append agreement test (P0-2 + P1-6).

## Notes for the next agent

- Do **not** treat the fast-suite failure as something this review introduced — it
  pre-exists (`.pi/` was committed earlier). Verify with `git status` (clean tree
  outside this mission folder).
- Re-measure line numbers before acting on any finding; the codebase is actively
  curated (recent Silverstone/Fuji/Sebring/Le Mans commits).
- This mission has **no `testFeatures` entry** and needs none — it ships no code.