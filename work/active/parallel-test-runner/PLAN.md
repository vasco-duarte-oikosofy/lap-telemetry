# Mission: Parallel Test Runner

**Spec:** [`docs/specs/parallel-test-runner.md`](../../docs/specs/parallel-test-runner.md)

**Goal:** Reduce full-suite test runtime from ~42 s to < 10 s by running independent tests concurrently, while preserving the agent-friendly output contract.

**Status:** 🔲 Planning

---

## Vertical slices

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-annotate-tests` | ✅ Complete | Every test script has a `// @parallel` header; sequential suite still passes |
| `02-parallel-runner-node` | 🔲 Not started | Runner executes Node-only tests in parallel; output contract matches current; single-test rerun still works |
| `03-parallel-runner-playwright` | 🔲 Not started | Runner executes Playwright tests in parallel with bounded concurrency; full suite < 10 s on dev machine |
| `04-runner-self-test` | 🔲 Not started | Self-test verifies runner output format and exit-code behaviour with tiny fixture scripts |

---

## Context

- 36 test scripts (18 pure Node, 18 Playwright), ~42 s sequential
- All Playwright tests are already isolated (random port, separate report dirs)
- Dev machine has 14 cores
- Current runner: `dev/scripts/test-summary.sh` (sequential bash loop)