# Slice 06 — Protocol enforcement meta-test

## Goal

Ensure every test script in the suite emits `[PASS]`/`[FAIL]` lines that the
parallel runner can count. Catch silently-broken tests that produce zero
counted assertions — the same class of bug that slice 02 fixed (3 tests
crashed with exit 1 but produced no `[FAIL]` lines, so the old runner
counted them as passing with 0 assertions) and that slice 04 caught again
(`test_static_track_outline_contract.js` used `assert` instead of the
custom `[PASS]`/`[FAIL]` logger).

## Context

The parallel runner counts assertions by grepping for `\[PASS\]` or
`^\s+PASS ` in each test's stdout. Any test that uses Node's built-in
`assert`, `console.log`, or emoji-based output (📸 ✔ ✖) without the
`[PASS]`/`[FAIL]` protocol will be counted as 0 assertions. If such a test
breaks silently, the runner won't detect it.

This has happened twice already:
- Slice 02 fixed 3 tests that produced 0 assertions (798 → 833).
- Slice 04 fixed `test_static_track_outline_contract.js` which used Node
  `assert` and produced 0 counted lines (added 81 assertions: 842 → 923).

## Steps

1. **Create `dev/scripts/test_protocol_enforcement.js`** — a meta-test that:
   - Reads the test script list from `package.json` (same source as the runner)
   - Runs each test with `NODE_OPTIONS=--timeout=60000` (or similar)
   - Checks that every test produces ≥ 1 line matching `/\[PASS\]|\[FAIL\]/`
   - Fails with a clear message naming any test that produces zero protocol lines
   - Uses `-- @parallel true` so it runs in the suite itself

2. **Run `bash scripts/test-summary.sh`** — must pass, including the new meta-test.

3. **Commit.**

## Acceptance

- `test_protocol_enforcement.js` passes when all suite tests emit ≥ 1 `[PASS]`/`[FAIL]` line.
- If a test is later modified to drop the protocol, this meta-test fails.
- Meta-test line count stays under 60.
- Full suite: ALL PASS — N assertions across 38 test scripts.

## Non-goals

- Do not modify existing tests (that was slice 04's job).
- Do not change the runner's counting logic.