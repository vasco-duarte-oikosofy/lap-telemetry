# Learnings — Fix: Delta-T calculation must use the exact same code as the web UI

## What surprised us

1. **computeKeepIndices affects ALL channels, not just lap_time_s.** The web JS applies the keep filter to speed, throttle, brake, and every other channel before resampling. Our original Python code resampled raw data without filtering boundary-artifact frames. This means ALL resampled grids could potentially differ from the web UI, not just delta_t. The impact was small for Barcelona (few or no boundary-artifact frames in the fixture), but it would be significant on lap data that starts immediately after a pit exit.

2. **smoothLapTime is essential for delta_t accuracy.** Without it, two laps' clock ticks land at different distances, creating ±200 ms sawtooth jitter in the raw delta_t. The smoothing bridges each 5 Hz plateau by distributing the next tick's increment across the held frames. This alone changes delta_t[2158] from ~424 ms to ~436 ms on the Barcelona fixture.

3. **smoothDt attenuates plateau-alignment residual jitter by ~6×.** Even after smoothLapTime, two laps' clock ticks land at slightly different distances (1-2 frames of recorder phase offset), creating ~20 ms jitter at each tick boundary. The 41-bin boxcar (±20 m) reduces this to ~3 ms. Adjacent-bin jumps in the smoothed trace are well under 10 ms; raw would be ~20 ms.

4. **Node.js subprocess IPC is fast enough.** Piping JSON through stdin/stdout adds ~200 ms per pipeline call on the Barcelona fixture (~635 KB input, ~100 KB output). For offline coaching, this is negligible. For real-time coaching at 1 Hz (one comparison per second), it would also be fine.

5. **`sys.executable.replace("python", "node")` doesn't work on systems where Python is `python3`.** Use `"node"` directly, since Node.js is always on PATH for this project (it's needed for the build).

6. **The ES module reparsing warning is harmless but noisy.** Node.js warns "Reparsing as ES module" when it first encounters import syntax in a .mjs file. Redirecting stderr to /dev/null in production code is fine; the subprocess.run() call only checks returncode.

## Design decisions

1. **Option A (Node.js as golden source) chosen over Option B (Python port).** The user explicitly requested using the Node.js module as the single source of truth. This eliminates drift risk entirely — the same code runs in both the web UI and the Python coaching engine. The only downside is the Node.js runtime dependency, which is already present (needed for the build).

2. **All channels piped through JS, not just lap_time_s.** The user emphasized we must use the exact same code for ALL parameters. This means computeKeepIndices filtering applies to speed/throttle/brake resampling too, not just delta_t computation.

3. **Contract tests use user-confirmed values.** The fix document recorded +436 ms at 2158 m and +331 ms at 2439 m from the web UI. The contract test verifies the JS pipeline matches within 0.5 ms. This is the most reliable regression guard — if the pipeline drifts, these tests will catch it immediately.

## Edge cases handled

- Missing throttle/brake columns → JS returns null, Python uses None
- Empty distance arrays → JS produces zero-filled bins
- Node.js not found → FileNotFoundError with clear message
- Subprocess timeout → 30 second limit prevents hangs