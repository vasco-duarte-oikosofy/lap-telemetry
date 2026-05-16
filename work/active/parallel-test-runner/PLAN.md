# Mission: Parallel Test Runner

**Spec:** [`docs/specs/parallel-test-runner.md`](../../docs/specs/parallel-test-runner.md)

**Goal:** Reduce full-suite test runtime from ~42 s to < 10 s by running independent tests concurrently, while preserving the agent-friendly output contract.

**Status:** 🔲 Planning

---

## Vertical slices

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-annotate-tests` | ✅ Complete | Every test script has a `// @parallel` header; sequential suite still passes |
| `02-parallel-runner-node` | ✅ Complete | Runner executes all @parallel true tests concurrently; output contract matches; single-test rerun works; 3 silently-broken tests fixed |
| `03-parallel-runner-playwright` | 🔲 Not started | Dual-pool concurrency (Node unlimited, PW bounded); ~15 s wall-time; spec updated with realistic target |
| `04-runner-self-test` | 🔲 Not started | Self-test verifies runner output format and exit-code behaviour with tiny fixture scripts |

---

## Context

- 36 test scripts (18 pure Node, 18 Playwright), ~42 s sequential
- All Playwright tests are already isolated (random port, separate report dirs)
- Dev machine has 14 cores
- Current runner: `dev/scripts/test-summary.sh` (sequential bash loop)