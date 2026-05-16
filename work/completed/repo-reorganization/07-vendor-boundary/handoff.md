# Handoff: 07-vendor-boundary

## State

Complete. Third-party shared-memory dependency submodules now live under `vendor/`, and the recorder can still import both LMU and rFactor 2 bindings from a source checkout.

## Changed files

- Moved submodules:
  - `pyLMUSharedMemory` → `vendor/pyLMUSharedMemory`
  - `pyRfactor2SharedMemory` → `vendor/pyRfactor2SharedMemory`
- Updated `.gitmodules` paths to the new `vendor/` locations.
- Updated `product/python/lap_telemetry/recorder/connect.py` to add the repository `vendor/` directory to `sys.path` for source-checkout imports.
- Added `dev/scripts/test_repo_reorg_vendor_boundary.js` and included it in `package.json`.
- Extended `dev/scripts/test_track_outline_recorder_channels.js` so recorder tests import both shared-memory plugin modules from the new vendor boundary.
- Updated vendor/submodule references in `README.md`, `CLAUDE.md`, `docs/SETUP.md`, `docs/DESIGN.md`, `docs/ARCHITECTURE.md`, `pyproject.toml`, and `vendor/README.md`.
- Updated `work/active/repo-reorganization/PLAN.md` to mark this slice complete.

## Validation

- `bash scripts/test-summary.sh` passed: 789 assertions across 35 test scripts.
- `npm run build` passed and wrote `product/dist/compare.html`.

## Important context

- `NEXT_STEPS.md` still has unrelated local modifications that predated this slice.
- `README.md` still has unrelated local modifications in the Record section that predated this slice; only vendor-path changes from this slice should be committed if preserving separation.
- `work/active/repo-reorganization/05-product-subtree/learnings.md` still has unrelated local modifications that predated this slice.
- `AGENTS.md` still references old docs/bundle paths and was not edited because it requires explicit approval.

## Next slice

The repository reorganization plan has no further planned slices after `07-vendor-boundary`.
