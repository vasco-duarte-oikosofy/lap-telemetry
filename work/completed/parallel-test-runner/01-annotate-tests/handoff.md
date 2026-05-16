# Slice 01 — Handoff

## What changed

- **36 test scripts** in `dev/scripts/` now have a `// @parallel true` header comment.
  - 7 files: annotation after `'use strict'`
  - 29 files: annotation after the header comment block (`*/` or first `//` line)

- **New files:**
  - `docs/specs/parallel-test-runner.md` — stable spec for the mission
  - `docs/specs/README.md` — updated to list the new spec
  - `work/active/parallel-test-runner/PLAN.md` — mission plan with slice table
  - `work/active/parallel-test-runner/01-annotate-tests/prompt.md` — slice prompt

## What's on disk

- `dev/scripts/test-summary.sh` — unchanged; still runs sequentially via `dev/scripts/test-summary.sh`
- All 36 test scripts — only change is the added `// @parallel true` line; no logic changed
- Full suite: ALL PASS — 798 assertions across 36 test scripts in ~42s

## Feature flags

- None for this slice. The `@parallel` annotation is purely metadata; the runner doesn't exist yet.

## Deferred TODOs

- Slice 02: build `dev/scripts/run-tests-parallel.js` that reads the annotations and runs parallel-safe tests concurrently
- Slice 03: extend the runner to handle Playwright tests with bounded concurrency
- Slice 04: self-test for the runner's output format and exit codes