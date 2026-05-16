# Slice 05 — Learnings

## What surprised us

1. **Zero-assertion detection was missing from the runner.** A script that exits 0 with no `[PASS]`/`[FAIL]` output was counted as "passing with 0 assertions" rather than flagged as a failure. This is exactly the bug class from slices 02/04 — tests that crash silently or use an incompatible assert library. Added `countPasses(r.output) === 0` as a failure condition in both `printSummary` and `runSingleTest`.

2. **Meta-test assertion messages must not contain `[FAIL]` or `[PASS]` as bare literals.** The runner's `extractFailures` regex matches `[FAIL]` anywhere in a line. A test named `detects [FAIL]` would be misidentified as a failing script. All assertion messages now use descriptions like "detects FAIL" instead of "detects [FAIL]".

3. **`require.main === module` guard is essential.** Without it, `require('./run-tests-parallel')` in the meta-test would execute `main()` and exit the process. Added the standard Node guard so the runner's functions can be imported for unit testing without side effects.

4. **Fixture scripts don't need to be in `package.json`.** They're only invoked by the meta-test via the runner's single-test mode. The runner discovers suite tests from `package.json`, but single-test mode takes any path.

5. **Capturing `console.log` for `printSummary` testing.** The meta-test temporarily replaces `console.log` to capture `printSummary` output, then restores it. This avoids needing to spawn subprocesses for unit tests while keeping the runner's output format unchanged.