# Slice Prompt: 04-development-area

## Goal

Move development-only tooling and tracked development inputs under `dev/` while preserving stable root commands needed by current automation.

## Execution order

1. Create this slice folder with `prompt.md`, `artifacts/`, `handoff.md`, and `learnings.md`.
2. Move development script implementations from `scripts/` to `dev/scripts/`.
3. Keep root `scripts/` compatibility wrappers for required stable commands.
4. Move `tools/` to `dev/tools/`.
5. Move tracked `sessions/` data to `dev/sessions/`.
6. Move root development helpers:
   - `verify_deltat.py` to `dev/tools/verify_deltat.py`
   - `run-map-visualization-phases.zsh` to `dev/scripts/run-map-visualization-phases.zsh`
7. Update package/test/build paths and session references.
8. Add orientation README files for development subfolders and compatibility wrappers.
9. Run `bash scripts/test-summary.sh`.
10. Run `npm run build`.
11. Update mission `PLAN.md`, handoff, and learnings.
12. Commit this slice only.

## Non-goals

- Do not move production source files into `product/`.
- Do not move stable docs into `docs/`.
- Do not archive historical root plans.
- Do not move vendor/submodule code.
