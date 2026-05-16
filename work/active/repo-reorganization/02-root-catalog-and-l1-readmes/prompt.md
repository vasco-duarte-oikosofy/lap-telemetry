# Slice Prompt: 02-root-catalog-and-l1-readmes

## Goal

Add a root catalog and orientation README files for the proposed L1 folders without moving existing production, development, vendor, test-output, or archive files.

## Execution order

1. Create this slice folder with `prompt.md`, `artifacts/`, `handoff.md`, and `learnings.md`.
2. Add `CATALOG_INDEX.md` at the repository root.
3. Add orientation README files for proposed L1 folders not already documented.
4. Update `work/active/repo-reorganization/PLAN.md` so completed slices are easy to scan with an emoji.
5. Run `bash scripts/test-summary.sh`.
6. Run `npm run build`.
7. Update handoff and learnings.
8. Commit this slice only.

## Non-goals

- Do not move source files.
- Do not move `sessions/` yet.
- Do not move test outputs yet.
- Do not archive historical root files yet.
- Do not change build or runtime paths.
