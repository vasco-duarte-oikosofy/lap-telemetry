# Handoff: 04-development-area

## State

Complete. Development-only tooling and tracked development inputs now live under `dev/`, with root compatibility wrappers for stable commands.

## Changed files

- Moved script implementations from `scripts/` to `dev/scripts/`.
- Added root compatibility wrappers:
  - `scripts/test-summary.sh`
  - `scripts/bundle.js`
  - `scripts/README.md`
- Moved `tools/` to `dev/tools/`.
- Preserved and updated `dev/tools/README-GENERATE-OUTLINE.md`, and linked it from both `dev/tools/README.md` and `dev/scripts/README.md`.
- Moved tracked `sessions/` data to `dev/sessions/`.
- Removed tracked `sessions/.DS_Store`; `.DS_Store` is already ignored.
- Moved root helpers:
  - `verify_deltat.py` to `dev/tools/verify_deltat.py`
  - `run-map-visualization-phases.zsh` to `dev/scripts/run-map-visualization-phases.zsh`
- Updated `package.json` to run tests/build implementation scripts from `dev/scripts/`.
- Updated test/build script root and session paths for the new layout.
- Added `dev/scripts/README.md`, `dev/tools/README.md`, and `dev/sessions/README.md`.
- Updated `work/active/repo-reorganization/PLAN.md` to mark this slice complete.

## Validation

- `bash scripts/test-summary.sh` passed: 731 assertions across 33 test scripts.
- `npm run build` passed.

## Important context

- `bash scripts/test-summary.sh` remains the stable agent command.
- Focused re-runs accept both new paths like `dev/scripts/test_f1f2.js` and old-style `scripts/test_f1f2.js` arguments.
- `npm run build` now calls `node dev/scripts/bundle.js`; `scripts/bundle.js` remains as a compatibility wrapper.
- `dev/sessions/` is tracked development data and should not be ignored or moved to `var/`.

## Next slice

`05-product-subtree` should move production/final code into `product/` and update build/runtime paths so the subtree is extractable.
