# Handoff: 06-docs-and-work-archive

## State

Complete. Stable documentation now lives under `docs/`, stable specs under `docs/specs/`, and historical planning/handoff/RCA documents under `work/archived-plans/`.

## Changed files

- Added regression coverage in `dev/scripts/test_repo_reorg_docs_archive.js` and included it in `package.json` test order.
- Moved root stable docs into `docs/`:
  - `ARCHITECTURE.md`, `DESIGN.md`, `RENDER_DESIGN.md`, `SETUP.md`, `TESTING_LESSONS.md`, `TEST_FIX_STATUS.md`, `track-heatmap-spec.md`.
- Moved root `specs/*.md` into `docs/specs/`.
- Moved historical root planning/handoff/RCA docs and old `archive/*.md` into `work/archived-plans/`.
- Updated README, stable docs, code comments, and `dev/scripts/run-map-visualization-phases.zsh` references to the new paths.
- Updated `docs/README.md`, `docs/specs/README.md`, and `work/archived-plans/README.md` orientation notes.
- Updated `work/active/repo-reorganization/PLAN.md` to mark this slice complete.

## Validation

- `bash scripts/test-summary.sh` passed: 778 assertions across 34 test scripts.
- `npm run build` passed and wrote `product/dist/compare.html`.

## Important context

- `NEXT_STEPS.md` still has unrelated local modifications that predated this slice and were not part of the docs/archive move.
- `work/active/repo-reorganization/05-product-subtree/learnings.md` still has unrelated local modifications that predated this slice.
- `AGENTS.md` still references the old `TESTING_LESSONS.md` and `dist/compare.html` paths; it was not edited because the standing rule requires explicit approval before modifying `AGENTS.md`.

## Next slice

`07-vendor-boundary` should clarify third-party/submodule ownership under `vendor/` and update submodule/docs references.
