# Slice 06 — Learnings

## What surprised us

1. **Assertion message content can trigger false-positive `[FAIL]` detection by the runner.** The initial assertion message `emits [PASS]/[FAIL] protocol` contained the literal string `[FAIL]`, which the runner's `extractFailures` regex matches. Every line of output was counted as both a PASS and a FAIL, causing the runner to report the test as failed. The fix: use descriptions like `follows PASS/FAIL protocol` instead of embedding `[PASS]`/`[FAIL]` in message text.

2. **Static analysis is faster and simpler than runtime analysis for protocol enforcement.** Reading each test file's source and checking for `[PASS]`/`[FAIL]`/`[${status}]` patterns runs in milliseconds, avoids test suite recursion (running the suite inside the suite), and catches the exact bug class (tests using `assert()` without protocol output).

3. **The `[${status}]` pattern is the dominant protocol pattern.** 28 of 39 tests use a custom `assert()` function that emits `[${status}]` (which produces `[PASS]` or `[FAIL]`). Only 9 tests have literal `[PASS]`/`[FAIL]`. The regex must match both.

4. **The meta-test checks itself.** Since `test_protocol_enforcement.js` is in `package.json`'s test list, it verifies its own source file contains protocol patterns. This is automatic and correct — the meta-test uses `[PASS]`/`[FAIL]` in its own `assert()` function.