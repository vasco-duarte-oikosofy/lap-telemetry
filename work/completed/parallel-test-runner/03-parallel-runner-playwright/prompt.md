# Slice 03 — Dual-pool concurrency for Node and Playwright tests

## Goal

Optimise the parallel runner to use separate concurrency pools for pure-Node
tests (unlimited) and Playwright tests (bounded), reducing full-suite wall-time
from ~18 s to ~15 s. Document why the < 10 s spec target is not achievable
without optimising the slow Python-invoking tests.

## Context from slice 02

The current runner uses a single concurrency pool (default `min(cpus-2, 6)`)
for all 36 tests. This works but is suboptimal because:

- **18 pure-Node tests** are lightweight (most < 0.2 s) and can run all at once
  with no resource contention.
- **4 Node+Python integration tests** are slow (2.7–7 s) because they spawn
  `python3` subprocesses. Two of them also re-invoke `test_width_profile_export.js`
  via `spawnSync`, creating redundant work when the suite already runs that
  test independently.
- **18 Playwright tests** each launch Chromium (~100–200 MB RAM) and need
  bounded concurrency to avoid memory pressure.

Timings on the dev machine (14-core Mac):

| Configuration | Wall-time |
|---|---|
| Sequential (old bash runner) | ~42 s |
| Single pool, concurrency 6 | ~17 s |
| Single pool, concurrency 12 | ~16 s |
| **Dual pool (Node unlimited, PW 8)** | **~15 s** |

The theoretical floor is ~14 s, limited by `test_width_profile_smoothing.js`
(6.9 s — spawns Python3). Getting under 10 s requires optimising those 4
Python-invoking tests, which is out of scope for this mission.

## Steps

1. **Classify tests into Node and Playwright pools.** The runner already
   scans each file's `// @parallel` annotation. Extend discovery to also
   detect `require('playwright')` or `require('chromium')` and tag the
   test as Playwright. Tests without Playwright go in the Node pool.

2. **Run both pools concurrently.** Start both `runConcurrently(nodePool,
   nodePool.length)` and `runConcurrently(pwPool, pwConcurrency)` at the
   same time via `Promise.all`. Node tests complete in < 1 s (except the
   4 Python-heavy ones which overlap with Playwright anyway).

3. **Set Playwright concurrency dynamically.** Default to
   `min(cpus().length - 2, 8)`. The `--concurrency` flag still works but
   applies to the Playwright pool; Node tests always run unlimited.

4. **Update `docs/specs/parallel-test-runner.md`** — adjust the < 10 s
   target expectation to document the ~15 s practical minimum and the
   bottleneck (Python-invoking tests).

5. **Run `bash scripts/test-summary.sh`** — must pass, must print the
   same `ALL PASS — N assertions across M test scripts in Xs` format.

6. **Commit.**

## Acceptance

- Full suite passes: `ALL PASS — 833 assertions across 36 test scripts`.
- Single-test rerun works unchanged.
- Wall-time is ~15 s on the dev machine (improved from ~18 s).
- `docs/specs/parallel-test-runner.md` documents the realistic target.
- Runner line count stays under 200.

## Non-goals

- Do not optimise the 4 Python-invoking tests (that is a separate mission).
- Do not change individual test scripts.
- Do not add shared-browser-context optimisation for Playwright tests.