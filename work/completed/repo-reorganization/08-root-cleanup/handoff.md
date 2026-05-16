# Handoff: 08-root-cleanup

## State

Complete. Legacy root `phases_*` execution-history directories now live under `work/archived-plans/`, and a regression test guards the tracked root directory boundary.

## Changed files

- Added `08-root-cleanup` to `docs/specs/repo-reorganization.md` requirements and `work/active/repo-reorganization/PLAN.md`.
- Added regression coverage in `dev/scripts/test_repo_reorg_root_cleanup.js` and included it in `package.json`.
- Moved legacy phase directories:
  - `phases_TUMFTM_based_track_map_outline/` → `work/archived-plans/phases_TUMFTM_based_track_map_outline/`
  - `phases_track_heatmap/` → `work/archived-plans/phases_track_heatmap/`
  - `phases_track_outline/` → `work/archived-plans/phases_track_outline/`
- Updated `docs/specs/TRACK_OUTLINE_APEX_DISTANCE.md` so future work no longer instructs agents to write to root `phases_track_outline/`.
- Updated `work/archived-plans/README.md` to mention legacy `phases_*` directories.
- Added this slice's prompt, artifacts README, learnings, and handoff.

## Validation

- `bash scripts/test-summary.sh` passed: 796 assertions across 36 test scripts.
- `npm run build` passed and wrote `product/dist/compare.html`.

## Important context

- `NEXT_STEPS.md` still has unrelated local modifications that predated this slice.
- `README.md` still has unrelated local modifications in the Record section that predated this slice.
- `work/active/repo-reorganization/05-product-subtree/learnings.md` still has unrelated local modifications that predated this slice.
- Archived phase prompts/handoffs may mention their old root paths as historical references; those were not rewritten.

## Next slice

No further repo-reorganization slices are currently planned.
