# 08-root-cleanup

Execute only this slice of `work/active/repo-reorganization/PLAN.md`.

## Goal

Move legacy root-level phase directories under `work/archived-plans/` so the tracked repository root only exposes documented L1 areas plus intentional root compatibility wrappers/configuration.

## Acceptance

- No tracked root directory remains for legacy `phases_*` work history.
- Legacy phase directories are preserved under `work/archived-plans/`.
- References needed by specs/docs point at the new paths or no longer instruct agents to create legacy root phase directories.
- `bash scripts/test-summary.sh` and `npm run build` pass.
