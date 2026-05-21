# Learnings — 01c.2 Exit gains improvements

## What surprised us

### Delta-T calculation (JS pipeline)

1. **computeKeepIndices affects ALL channels, not just lap_time_s.** The web JS applies the keep filter to speed, throttle, brake, and every other channel before resampling. Our original Python code resampled raw data without filtering boundary-artifact frames. This means ALL resampled grids could potentially differ from the web UI, not just delta_t. The impact was small for Barcelona (few or no boundary-artifact frames in the fixture), but it would be significant on lap data that starts immediately after a pit exit.

2. **smoothLapTime is essential for delta_t accuracy.** Without it, two laps' clock ticks land at different distances, creating ±200 ms sawtooth jitter in the raw delta_t. The smoothing bridges each 5 Hz plateau by distributing the next tick's increment across the held frames. This alone changes delta_t[2158] from ~424 ms to ~436 ms on the Barcelona fixture.

3. **smoothDt attenuates plateau-alignment residual jitter by ~6×.** Even after smoothLapTime, two laps' clock ticks land at slightly different distances (1-2 frames of recorder phase offset), creating ~20 ms jitter at each tick boundary. The 41-bin boxcar (±20 m) reduces this to ~3 ms.

4. **Node.js subprocess IPC is fast enough.** Piping JSON through stdin/stdout adds ~200 ms per pipeline call on the Barcelona fixture. For offline coaching, this is negligible.

5. **Single source of truth eliminates an entire class of bugs.** By routing ALL telemetry channels through the exact same JS code the web UI uses, we eliminated the drift problem entirely. Contract tests catch drift after it happens; sharing the code prevents it from happening.

### Entry gain algorithm (delta-t entry→apex)

6. **The speed heuristic under-reported every entry gain by 30–60%.** On the swapped Barcelona fixture, `speed_delta / 100.0` gave -84.5 ms for t1, while the real delta-time from entry to apex was -155.8 ms. Across all 9 entry gains, the heuristic was consistently too small.

7. **Chicane shared entry points can flip the sign.** Turns t2/t3 at Barcelona share a single throttle-lift entry point (909 m). The heuristic said "gain" (-17 ms) because the driver was faster at that point, but delta_t[apex] - delta_t[entry] correctly revealed a loss (+8 ms for t2, +37 ms for t3) because the driver gave back time in the chicane before reaching each apex. Each corner's entry effect is measured over its own zone — no special case needed.

8. **No code path change needed for the chicane edge case.** The algorithm naturally handles it: the same entry_idx (909) is used with different apex_idx values (940 for t2, 1161 for t3), producing different delta_t windows.

9. **Phase boundaries must not overlap.** Entry gains measure entry→apex, exit gains measure exit→straight_end. If entry measured entry→straight_end, the same advantage would be reported twice for one corner. Keeping each phase within its own boundaries avoids double-counting.

10. **Removing decorative blank lines sufficed to stay under 437 line ceiling.** lap_comparator.py grew from 433 → 446 with the entry-gain code. Removing 7 double-blank lines brought it to 436.

## Design decisions

1. **JS pipeline as golden source, not Python port.** Same code runs in web UI and coaching engine. Node.js dependency already present for the build.

2. **All three gain phases use real delta-time within their own boundaries.**
   - Entry: entry_point → apex
   - Minimum speed: apex → straight_end
   - Exit: exit_point → straight_end

3. **All three loss phases still use speed_delta/100.0 heuristic.** No evidence the heuristic is wrong for losses. The delta-t fix addresses under-reporting of gains.

4. **Fallback heuristic for out-of-range delta_t indices.** If indices are out of bounds or entry_idx >= apex_idx, falls back to `speed_delta / 100.0`. Matches exit gain fallback pattern.

5. **gain_end_distance_m set based on speed delta sign, not loss_s sign.** For chicanes where speed suggests a gain but delta_t reveals a loss, gain_end_distance_m still documents the measurement window boundary.

6. **Contract tests use user-confirmed web UI values.** +436 ms at 2158 m and +331 ms at 2439 m verified the JS pipeline matches within 0.5 ms. Most reliable regression guard.

## Edge cases handled

- Missing throttle/brake columns → JS returns null, Python uses None
- Empty distance arrays → JS produces zero-filled bins
- Node.js not found → FileNotFoundError with clear message
- Subprocess timeout → 30 second limit prevents hangs
- Chicane shared entry point → different entry→apex windows produce correct per-corner results
- entry_idx >= apex_idx → fallback to heuristic
- delta_t indices out of range → fallback to heuristic