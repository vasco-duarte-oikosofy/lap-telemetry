# Learnings — Slice 01c: Determine Entry/Exit Phase Algorithm

## What surprised us

1. **The speed heuristic under-reported every gain by 30–60%.** `speed_delta / 100.0` gave -84.5 ms for Barcelona t1 entry, while real delta-time from entry to apex was -155.8 ms. Every entry gain on the swapped fixture was under-reported.

2. **Chicane shared entry points can flip the sign.** t2/t3 at Barcelona share a throttle-lift at 909 m. The heuristic said "gain" but delta_t[apex] - delta_t[entry] correctly revealed a loss — the driver gave time back in the chicane.

3. **JS pipeline as single source of truth eliminates an entire class of bugs.** Contract tests catch drift after it happens; sharing the code prevents it from happening. computeKeepIndices affects ALL channels, not just lap_time_s.

4. **smoothLapTime is essential for delta_t accuracy.** Without it, ±200 ms sawtooth jitter. With it, delta_t[2158] matches the web UI to within 0.5 ms.

5. **Entry throttle-lift detection walks FORWARD, not backward.** The meaningful lift point is where throttle first drops below threshold when scanning from the look-back start toward the apex.

6. **End of straight = next corner's entry point**, not the next corner's zone boundary. Zone boundaries can be 50-100 m off.

7. **Phase boundaries must not overlap.** Entry→apex, apex→straight_end, exit→straight_end. If entry measured entry→straight_end, the same advantage would be double-counted.

8. **Pre-existing oversized files must be split at the right granularity.** The delta-time & gains test group was ~377 lines of test code — too large for a single file with preamble. Three-way split (phase detection, delta-time/gains, JS contract) was the natural boundary.

9. **Python test scripts need Node.js wrappers to join the parallel runner.** The runner discovers scripts from package.json and runs them with `node`. Wrappers use `// @parallel true`, explicit PYTHONPATH, and `[PASS]`/`[FAIL]` in source for protocol enforcement.

10. **Feature-specific test suites keep feedback under 5 seconds.** `--feature interactive-race-coach` runs 7 scripts in 1.3s vs 50 scripts in 11s.

## Edge cases handled

- Missing throttle/brake columns → JS returns null, Python uses None
- Chicane shared entry point → different entry→apex windows produce correct per-corner results
- entry_idx >= apex_idx → fallback to heuristic
- delta_t indices out of range → fallback to heuristic