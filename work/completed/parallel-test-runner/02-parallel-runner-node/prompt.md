# Slice 02 — Build the parallel runner

## Goal

Replace the sequential bash runner with a Node parallel runner that runs
`@parallel true` tests concurrently (bounded concurrency) and `@parallel false`
tests sequentially after. The public CLI (`bash scripts/test-summary.sh`)
remains unchanged.

## Steps

1. Write `dev/scripts/run-tests-parallel.js` — the parallel test runner.
2. Update `dev/scripts/test-summary.sh` to delegate to the Node runner.
3. Run `bash scripts/test-summary.sh` — must produce identical output format
   and all 798 assertions must pass.
4. Verify the full suite runs faster than the old sequential 42 s baseline.
5. Verify single-test rerun (`bash scripts/test-summary.sh dev/scripts/test_f1f2.js`)
   still works.
6. Commit.

## Acceptance

- `bash scripts/test-summary.sh` exits 0 and prints `ALL PASS — 798 assertions across 36 test scripts in Xs`.
- `bash scripts/test-summary.sh dev/scripts/test_f1f2.js` exits 0 and shows per-test result.
- Full suite wall-time is measurably faster than sequential (target: < 20 s for this slice).
- Runner uses only Node built-ins (no new npm dependencies).
- `--concurrency` flag works.

## Non-goals

- Do not write a formal self-test yet (slice 04).
- Do not change individual test scripts or their output format.
- Do not change the public CLI interface.