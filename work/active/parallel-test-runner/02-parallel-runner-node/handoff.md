# Slice 02 — Handoff

## What changed

### New files
- `dev/scripts/run-tests-parallel.js` — parallel test runner (153 lines)
  - Reads `// @parallel true/false` annotations from test files
  - Runs `@parallel true` tests concurrently (default concurrency: `min(cpus-2, 6)`)
  - Runs `@parallel false` tests sequentially after
  - Detects failures via both `[FAIL]` regex and non-zero exit codes
  - `--concurrency N` flag for tuning
  - Preserves `ALL PASS — N assertions across M test scripts in Xs` output contract

### Modified files
- `dev/scripts/test-summary.sh` — now delegates to Node runner (sets PYTHONPATH first)
- `dev/scripts/test_static_outline_runtime_rendering.js` — fixed removed import, wrong attribute check, added `[PASS]`/`[FAIL]` protocol
- `dev/scripts/test_m6_extras.js` — fixed `WEB_DIR` path (`web/` → `product/web/`), `REPO` → `ROOT`
- `dev/scripts/test_manual_outline_align.js` — fixed HTML path (`tools/` → `dev/tools/`), added `[PASS]`/`[FAIL]` protocol
- `docs/TESTING_LESSONS.md` — added L0 rule about `[PASS]`/`[FAIL]` protocol

## What's on disk now

- Full suite: **ALL PASS — 833 assertions across 36 test scripts in 17s**
- Single-test rerun: `bash scripts/test-summary.sh <file>` works
- Build: `npm run build` succeeds

## Feature flags

- None for the runner. Concurrency is controlled by `--concurrency N`.

## Deferred TODOs

- Slice 03 (PLAN.md): Extend runner with Playwright-specific concurrency tuning. Currently all `@parallel true` tests use the same pool — this may need refinement for memory-heavy Playwright tests.
- Slice 04 (PLAN.md): Self-test that verifies runner output format and exit codes with tiny fixture scripts.
- Consider: the 3 fixed tests were previously "passing" with 0 assertions. The assertion count went from 798 → 833 (9 + 17 + 9 = 35 new assertions).