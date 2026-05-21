# Learnings — 01c.3 Fix oversized modules

## What surprised us

1. **The delta-time & gains test group was too large for a single file.** The 01c.2 sub-slices added ~140 lines of tests (entry gain synthetic + fixture), pushing the delta-time group from ~250 to ~377 lines of test code. With preamble, that's 456 lines — over the ceiling. The original prompt estimated ~250 lines for this group, which was based on the pre-01c.2 line count.

2. **Each group needs its own minimal imports, not a copy of the full preamble.** The original 79-line preamble imported everything for all groups. By giving each test file only the imports it needs, we saved ~30 lines per file. This is what made `test_delta_time_gains.py` fit under 437 (377 test lines + 48 preamble = 375 total, after trimming unused imports).

3. **Node.js wrappers are needed for Python tests in the parallel runner.** The test-summary.sh delegates to `run-tests-parallel.js`, which discovers scripts from `package.json` and runs them with `node`. Python scripts can't be added directly. The workaround: thin Node.js wrappers that `spawnSync('python3', [script])` with explicit `PYTHONPATH`. This follows the same pattern as `test_coach_lap_comparison.js`.

4. **Protocol enforcement checks source files, not runtime output.** `test_protocol_enforcement.js` does static analysis — it checks if the `.js` source text contains `[PASS]`/`[FAIL]` patterns. A wrapper that just forwards Python output has no such patterns in its JS source. The fix: add the `ok()` + summary pattern to each wrapper, using `[PASS]`/`[FAIL]` for the wrapper's own assertion (that the Python test exited 0).

5. **Extracting phase detection functions dramatically reduced lap_comparator.py.** Moving `find_entry_point` (48 lines), `find_brake_point` (26 lines), `find_exit_points` (59 lines) + their docstrings to dedicated modules brought lap_comparator.py from 436 to 241 lines. That's 195 lines removed, well beyond the ≤370 target.

6. **Pre-existing oversized files are not this slice's problem.** Files like `test_f8f9f10f11.js` (549 lines) and `register_outline.py` (558 lines) already violated the ceiling. This slice only addressed the files identified in the prompt.

## Design decisions

1. **Three-way split of test file, not two-way.** The prompt suggested three groups, and the line counts confirmed this: phase detection (~381 with preamble), delta-time & gains (~375 with preamble), JS pipeline contract (~124 with preamble). A two-way split would have left the delta-time group over 437.

2. **`find_straight_end_after_corner` stays in lap_comparator.py.** It uses `find_entry_point` but is called from `compare_laps()`. Placing it in `entry_detection.py` would create a circular dependency risk. It's only 24 lines, so keeping it in the main file is fine.

3. **Node.js wrappers use `// @parallel true` and explicit PYTHONPATH.** This lets the Python tests run in the parallel pool with the rest of the suite, following the project's existing convention for Python-in-Node wrappers.