# Slice 03 — Handoff

## What changed

### Modified files
- `dev/scripts/run-tests-parallel.js` — dual-pool concurrency
  - Added `isPlaywright()` detection: scans for `require('playwright')` or `require('chromium')`
  - Split `@parallel true` tests into `nodePool` (unlimited concurrency) and `pwPool` (bounded concurrency)
  - Both pools run concurrently via `Promise.all`, then serial tests run after
  - `--concurrency` flag now applies to Playwright pool; Node pool always runs unlimited
  - Default PW concurrency: `min(cpus - 2, 8)` (was `min(cpus - 2, 6)`)
- `docs/specs/parallel-test-runner.md` — updated expected metrics table and concurrency docs

## What's on disk now

- Full suite: **ALL PASS — 923 assertions across 37 test scripts in ~6.5s**
- Single-test rerun: `bash scripts/test-summary.sh <file>` works unchanged
- Build: `npm run build` succeeds
- Runner line count: 168 (under 200 limit)

## Feature flags

- None. Concurrency controlled by `--concurrency N` (applies to PW pool only).

## Deferred TODOs

- Slice 05: Self-test that verifies runner output format and exit codes with tiny fixture scripts
- Slice 06: Protocol enforcement meta-test (ensures every test emits [PASS]/[FAIL])