# Slice 05 — Runner self-test

## Goal

Create a meta-test that verifies the parallel runner's output format and
exit-code behaviour using tiny fixture scripts. This is the runner's own
regression test — if someone changes `run-tests-parallel.js` and breaks
the summary format, assertion counting, or exit codes, this test catches
it.

## Context

The parallel runner at `dev/scripts/run-tests-parallel.js` has two modes:

1. **Full-suite mode** — discovers `@parallel true` scripts in
   `package.json`, classifies them into Node/PW pools, runs them, and
   prints either `ALL PASS — N assertions across M test scripts in Xs`
   or `FAILED — N passed, K of M scripts failed in Xs`.

2. **Single-test mode** — invoked with a script path, runs just that
   script, prints `PASS — N assertions in Xs (script)` or `FAIL — script`.

The runner has no test coverage. Slice 02 fixed 3 silently-broken tests
that the old runner missed, and slice 04 fixed another. A change to the
runner's regex patterns, summary format, or exit-code logic could break
the output contract without anyone noticing.

## Steps

1. **Create fixture scripts** in a subdirectory (e.g.
   `dev/scripts/lib/__runner-fixtures__/`):

   - `fixture-pass.js` — exits 0, prints `  [PASS] ok` (1 assertion)
   - `fixture-fail.js` — exits 1, prints `  [FAIL] broken` (1 failure)
   - `fixture-zero.js` — exits 0, prints nothing (0 assertions — simulates a
     test that forgot to emit `[PASS]`/`[FAIL]`)

   Each fixture must have `// @parallel true` so the runner discovers it.
   Keep each fixture under 10 lines.

   The meta-test must **not** add these fixtures to `package.json`'s
   `scripts.test` field. Instead, the meta-test calls the runner's internal
   functions directly or passes a custom test list. Choose whichever
   approach keeps the runner under 200 lines and the meta-test under 60
   lines.

2. **Create `dev/scripts/test_runner_self_test.js`** — a meta-test that
   verifies:

   - **Success case**: running a fixture that passes produces `ALL PASS — 1
     assertions across 1 test scripts in Xs` and exit code 0.
   - **Failure case**: running a fixture that fails produces `FAILED` in
     output and exit code 1.
   - **Zero-assertion detection**: running a fixture that produces zero
     `[PASS]`/`[FAIL]` lines but exits 0 is treated as a failure (this is
     the bug class from slices 02/04 — the runner detects exit code 1 or
     `[FAIL]` lines).
   - **Single-test mode**: `runSingleTest` on a passing fixture prints
     `PASS — 1 assertions in` and exits 0.
   - **Assertion counting**: the `countPasses` regex correctly counts
     `[PASS]` lines in various formats (`  [PASS]`, `[PASS]`, `[PASS] with
     detail`).

   Use `// @parallel true` so the meta-test itself runs in the suite.

3. **Run `bash scripts/test-summary.sh`** — must pass, including the new
   meta-test. Assertion count increases by however many the meta-test
   asserts.

4. **Commit.**

## Acceptance

- `test_runner_self_test.js` passes and covers: success output format,
  failure output format, zero-assertion detection, single-test mode, and
  assertion counting.
- Meta-test line count stays under 60.
- Fixture scripts stay under 10 lines each.
- Runner (`run-tests-parallel.js`) stays under 200 lines total — if the
  meta-test needs to import runner internals, export them; do not
  duplicate logic.
- `bash scripts/test-summary.sh` exits 0 with all tests passing.
- No new npm dependencies.

## Non-goals

- Do not change the runner's logic or output format (that's what the
  meta-test protects, not what it modifies).
- Do not modify existing test scripts.
- This is NOT protocol enforcement (that's slice 06, which checks that
  every suite test emits `[PASS]`/`[FAIL]`). This slice tests the runner
  itself.