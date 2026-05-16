# 06-docs-and-work-archive

Execute only this slice of `work/active/repo-reorganization/PLAN.md`.

## Goal

Move stable documentation/specs under `docs/` and historical root planning/handoff/RCA documents under `work/archived-plans/`.

## Acceptance

- Root-level stable docs are now under `docs/`.
- Root `specs/` content is now under `docs/specs/`.
- Historical root planning, handoff, RCA, and legacy `archive/` documents are now under `work/archived-plans/`.
- References needed by code, scripts, and stable docs point at the new paths.
- `bash scripts/test-summary.sh` and `npm run build` pass.
