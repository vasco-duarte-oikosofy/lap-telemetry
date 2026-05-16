# Spec: Parallel Test Runner

## Goal

Reduce full-suite test runtime from ~42 s to under 10 s by running independent
tests concurrently, while preserving the agent-friendly output contract that
`bash scripts/test-summary.sh` already provides.

## Why it matters

TDD cadence depends on fast feedback. At 42 seconds the suite is already slow
enough that an agent (or human) waits between code-and-test cycles. As coverage
grows, sequential wall-time will only increase. A parallel runner protects the
feedback loop.

The current sequential runner (`dev/scripts/test-summary.sh`) launches each of
the 36 test scripts one after another. The hot-path bottleneck is the 18
Playwright tests: each one starts a Chromium process (~2 s of cold start) and
an HTTP server on a random port. The 18 pure-Node tests are faster (<0.5 s
each) but still add up in series.

## Current state

| Category       | Count | Avg per test | Total sequential |
|---------------|------:|:------------|:-----------------|
| Pure Node      |    18 | <0.5 s      | ~3 s             |
| Playwright     |    18 | ~2.5 s      | ~39 s            |
| **Full suite** |   36 |             | **~42 s**        |

Every Playwright test already calls `startServer()` which binds to **port 0**
(random available port) and writes to its own unique `var/test-output/`
subdirectory. No test depends on output from another test. This means all
current tests are safe to run in parallel with bounded concurrency.

## Expected benefit

| Metric                        | Before | After (target) | After (achieved) |
|-------------------------------|-------:|:---------------|:----------------- |
| Full-suite wall-time          | ~42 s  | < 10 s         | ~7 s             |
| Output contract               | same   | unchanged      | unchanged        |
| Single-test rerun             | works  | unchanged      | unchanged        |
| New-test opt-in               | none   | `// @parallel true` comment | `// @parallel true` comment |

With 14 cores available and a concurrency limit of 6 Playwright processes, 18
Playwright tests complete in 3 batches × ~2.5 s ≈ 7.5 s. The 18 Node tests
finish in under 1 s. Total ≈ 8 s.

## Requirements

1. **Public CLI unchanged.** `bash scripts/test-summary.sh` must continue to
   work for full-suite runs and `bash scripts/test-summary.sh <file>` for
   focused reruns. Agents must not need to learn a new command.

2. **Concurrent execution.** Tests annotated as parallel-safe run concurrently
   with a bounded concurrency limit. Tests not yet annotated (or annotated
   `@parallel false`) run serially after all parallel tests complete.

3. **In-file metadata.** Each test script declares `// @parallel true` or
   `// @parallel false` in its header. Missing annotation defaults to `false`
   (conservative — new tests opt in explicitly).

4. **Agent-friendly output preserved.** On success, print exactly one line:
   `ALL PASS — N assertions across M test scripts in Xs`. On failure, list
   only the failing script paths with their captured error output.

5. **Exit code.** Exit 0 iff every child process exits 0. Exit 1 otherwise.

6. **No new runtime dependencies.** The runner uses only Node built-ins
   (`child_process`, `os`, `fs`, `path`). No npm packages added.

7. **Self-test.** The runner itself has a test that verifies the summary output
   format and exit-code behaviour using tiny fixture scripts.

8. **Concurrency configurable.** A `--concurrency` flag (default:
   `min(os.cpus().length - 2, 6)`) allows tuning without editing code.

9. **Protocol enforcement.** Every test script in the suite must emit
   `[PASS]`/`[FAIL]` lines that the runner can count. A meta-test
   (`test_protocol_enforcement.js`) ensures no test silently produces zero
   counted assertions — the class of bug where a test crashes or uses an
   incompatible assert library and the runner reports 0 assertions instead
   of a failure. See slice `06-protocol-enforcement` in
   `work/active/parallel-test-runner/PLAN.md`.

## Out of scope

- Reorganising existing tests into suites or groups beyond parallel/serial.
- Changing how individual tests report assertions or capture screenshots.
- Replacing the Playwright test framework or changing per-test browser
  lifecycle (shared browser context is a later optimisation).