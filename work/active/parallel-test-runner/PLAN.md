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
| `03-parallel-runner-playwright` | ✅ Complete | Dual-pool concurrency (Node unlimited, PW bounded); suite ~6.5s; spec updated |
| `04-optimise-python-fixtures` | ✅ Complete | Batch Parquet fixture creation; remove redundant re-run tests; full suite ≈ 7 s (< 10 s target achieved) |
| `05-runner-self-test` | 🔲 Not started | Self-test verifies runner output format and exit-code behaviour with tiny fixture scripts |
| `06-protocol-enforcement` | 🔲 Not started | Meta-test ensures every test script in the suite emits \[PASS\]/\[FAIL\] protocol; catches silently-broken tests that produce zero counted assertions |

---

## Context

- 36 test scripts (18 pure Node, 18 Playwright), ~42 s sequential
- All Playwright tests are already isolated (random port, separate report dirs)
- Dev machine has 14 cores
- Current runner: `dev/scripts/test-summary.sh` (sequential bash loop)
- 4 Python-invoking Node tests are the wall-time bottleneck (2.6–7.6 s each)
  - Each calls `spawnSync('python3', ...)` up to 9 times to create synthetic Parquet fixtures
  - 10 sequential Python spawns take ~3 s; 1 batched spawn takes ~0.3 s (10× speedup)
  - 3 tests re-invoke other test scripts via `spawnSync('node', [...])`, adding redundant overhead
- Spec target remains < 10 s; achieving it requires both dual-pool concurrency AND Python fixture optimisation