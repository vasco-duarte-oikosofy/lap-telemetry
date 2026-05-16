# Slice Prompt: 03-untracked-output-isolation

## Goal

Isolate generated test outputs and local temporary files under untracked `var/` folders without moving tracked development data such as `sessions/`.

## Execution order

1. Create this slice folder with `prompt.md`, `artifacts/`, `handoff.md`, and `learnings.md`.
2. Update test scripts so generated reports are written under `var/test-output/`.
3. Add tracked orientation README files for `var/test-output/`, `var/screenshots/`, and `var/tmp/`.
4. Update `.gitignore` so generated `var/` contents and legacy root output folders stay untracked.
5. Remove previously tracked generated report/screenshot/temp files from Git.
6. Run `bash scripts/test-summary.sh`.
7. Run `npm run build`.
8. Update mission `PLAN.md`, handoff, and learnings.
9. Commit this slice only.

## Non-goals

- Do not move `sessions/`.
- Do not move production source files.
- Do not move development tools.
- Do not archive historical root plans.
