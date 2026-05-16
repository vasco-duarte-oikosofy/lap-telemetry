# Slice 03 — Learnings

## What surprised us

1. **Dual-pool is faster than expected.** Wall-time dropped from ~12.4 s (single pool) to ~6.5 s. The key insight: Node tests are so fast (<0.5 s total) that "unlimited concurrency" for them means they finish almost instantly, freeing resources for Playwright tests immediately.

2. **The `DEFAULT_CONCURRENCY` → `DEFAULT_PW_CONCURRENCY` rename needs care.** The variable was still referenced in `main()` as `DEFAULT_CONCURRENCY` after the rename, causing a runtime crash. Must update all references.

3. **Playwright detection via `require()` regex is reliable.** Using `/require\s*\(\s*['"](@?playwright|chromium)/` correctly identifies all 19 Playwright tests. No false positives among the 18 Node tests.

4. **Zero serial tests.** All 37 tests have `// @parallel true` (from slice 01), so the serial pool is always empty. The dual pool (Node unlimited + PW bounded) handles everything.

5. **`min(cpus - 2, 8)` for PW concurrency.** Upped from 6 to 8 — on a 14-core Mac this allows more overlap while staying within memory limits. 8 Chromium processes = ~1.6 GB RAM, well within budget.

6. **Slice 04 (Python fixtures) was already done.** The ~6.5 s time includes the batched Python fixture optimization from slice 04, which was completed before this slice. Without that, the floor would be ~14 s.