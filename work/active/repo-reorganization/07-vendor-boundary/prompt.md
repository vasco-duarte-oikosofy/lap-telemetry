# 07-vendor-boundary

Execute only this slice of `work/active/repo-reorganization/PLAN.md`.

## Goal

Clarify third-party/submodule ownership under `vendor/` and update submodule/docs references.

## Acceptance

- Shared-memory dependency submodules live under `vendor/`.
- `.gitmodules` points to the `vendor/` submodule paths.
- The recorder can still import/read the LMU and rFactor 2 shared-memory bindings from a source checkout.
- Docs and orientation files describe the vendor boundary.
- `bash scripts/test-summary.sh` and `npm run build` pass.
