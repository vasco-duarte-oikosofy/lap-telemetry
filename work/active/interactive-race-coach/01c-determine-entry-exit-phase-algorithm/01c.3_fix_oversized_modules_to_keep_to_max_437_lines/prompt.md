# Slice 01c.3 — Fix oversized modules to keep to max 437 lines

## Problem

Several modules exceed (or sit dangerously close to) the 437-line hard
ceiling mandated by `AGENTS.md`.  The worst offender is
`dev/scripts/test_phase_detection.py` at 817 lines — nearly **double**
the limit.  Other modules have already been trimmed (e.g.
`lap_comparator.py` was 626 → 433), but the structural fix (splitting
into focused files) has not been applied consistently.

## Current state

| File | Lines | Status |
|------|------:|--------|
| `dev/scripts/test_phase_detection.py` | 817 | ❌ exceeds by 380 |
| `product/python/lap_telemetry/coach/lap_comparator.py` | 433 | ⚠️ 4 lines of margin |
| Other `.py` files under `product/python/` | <200 | ✅ |

## Scope

### 1. Split `dev/scripts/test_phase_detection.py`

The file contains three natural test groups that map to separate files:

| Group | Tests | Approx lines | Target file |
|-------|-------|-------------:|-------------|
| Phase detection | `test_throttle_lift_*`, `test_brake_*`, `test_full_throttle_*`, `test_separate_exit_phases`, `test_merged_exit`, `test_speed_fallback_*`, `test_missing_channels_graceful`, `test_thresholds_configurable` | ~200 | `dev/scripts/test_phase_detection.py` |
| Delta-time & gains | `test_delta_time_trace_*`, `test_find_straight_end_*`, `test_minimum_speed_*`, `test_apex_offset_*` | ~250 | `dev/scripts/test_delta_time_gains.py` |
| JS pipeline contract | `test_js_pipeline_*` | ~100 | `dev/scripts/test_js_pipeline_contract.py` |

Rules for the split:
- Each new file is a self-contained test script (its own `main()`, own
  import block, own pass/fail counters).
- The shared helpers (`ok()`, `make_corner()`, `make_speed_trace()`,
  `ROOT` path constant, `pass_count`/`fail_count` globals) must be
  **duplicated** in each file (not shared via import).  This is the
  existing convention in this project's test scripts — each is
  standalone and runnable with a bare `python3 <path>`.
- The `test-summary.sh` runner must pick up the new files.  Add them
  to the `npm test` script string in `package.json` (the runner
  auto-discovers test scripts by naming convention, but the explicit
  list in `package.json` also needs updating).

### 2. Reduce `lap_comparator.py` margin

At 433 lines it has only 4 lines of margin.  Options:
- Extract `find_entry_point` + `find_brake_point` into a dedicated
  `entry_detection.py` module.
- Extract `find_exit_points` into `exit_detection.py`.
- Extract `find_straight_end_after_corner` alongside whichever
  module it fits best.

Goal: bring `lap_comparator.py` under 350 lines so there is room
to grow without constant trimming.

### 3. Verify every file stays under 437

After all splits, run `wc -l` on every changed file and confirm.
Run `bash scripts/test-summary.sh` to confirm all tests still pass
(including the new split files).

## Acceptance criteria

1. `dev/scripts/test_phase_detection.py` ≤ 437 lines.
2. All new test files ≤ 437 lines.
3. `product/python/lap_telemetry/coach/lap_comparator.py` ≤ 370 lines.
4. Every file in the project ≤ 437 lines.
5. `bash scripts/test-summary.sh` exits 0 with all test files (old + new) passing.
6. `npm run build` succeeds.
7. No test logic changes — only file splits and import updates.