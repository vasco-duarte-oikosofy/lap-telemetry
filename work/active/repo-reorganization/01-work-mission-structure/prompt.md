# Slice Prompt: 01-work-mission-structure

## Goal

Create the first mission slice for repository reorganization without moving production or development source files.

## Execution order

1. Create the stable spec at `docs/specs/repo-reorganization.md`.
2. Create `work/` state folders and document the mission convention in `work/README.md`.
3. Create `work/active/repo-reorganization/PLAN.md` with a spec link and vertical-slice status table.
4. Create this slice folder with `prompt.md`, `artifacts/`, `handoff.md`, and `learnings.md`.
5. Link the `work/` convention from `AGENTS.md`.
6. Stop tracking `.claude/` and ignore it going forward.
7. Run `bash scripts/test-summary.sh`.
8. Run `npm run build`.
9. Update handoff and learnings.
10. Commit this slice only.

## Non-goals

- Do not move production code.
- Do not move `sessions/` yet.
- Do not move root-level historical plans yet.
- Do not create `product/`, `dev/`, `vendor/`, or `var/` beyond documentation required by this slice.
