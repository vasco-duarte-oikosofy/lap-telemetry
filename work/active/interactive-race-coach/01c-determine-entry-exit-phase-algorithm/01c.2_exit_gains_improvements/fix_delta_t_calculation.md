# Fix: Delta-T calculation must use the exact same code as the web UI

## What we've already learned

### Speed integration was wrong (learning #8)

Our original `compute_delta_time_trace()` reconstructed cumulative time from speed (`1 / (speed_kph / 3.6)` summed over distance). This was an approximation that produced different values than the web UI. We already fixed this — `compute_delta_time_trace()` now takes resampled `lap_time_s` arrays directly (see `learnings.md` #8, `handoff.md` "Known issue ~~ FIXED" section).

**But we're still not matching the web JS.** We ported steps 4–5 of the pipeline (resample + forward-clamp + compute difference) but missed steps 1–2 and 6.

### What we fixed so far (commit e323ba3)

| Step | Web JS | Python | Status |
|------|--------|--------|--------|
| 3 | `resample(distances, lapTimeSmoothed, maxDist)` | `resample_column(dist, lap_time, track_length)` | ✅ Done |
| 4 | Forward-clamp (non-decreasing) | Forward-clamp loop | ✅ Done |
| 5 | `computeDeltaT(sessionLapTime, refLapTime)` | `compute_delta_time_trace(driver, ref, track_length)` | ✅ Done |

### What's still missing

| Step | Web JS | Python | Status |
|------|--------|--------|--------|
| 1 | `computeKeepIndices(lapTime, lapDist, start, end, trackLen)` | — | ❌ Missing |
| 2 | `smoothLapTime(lapTime, keepIndices)` | — | ❌ Missing |
| 6 | `smoothDt(dt, maxRadius=20)` | — | ❌ Missing |

### The user-confirmed values don't match

The user reported seeing delta_t = +436ms at 2158m and +331ms at next braking zone on the web UI. Our Python computed +423.5ms and +355.1ms at those distances. The discrepancy comes from the missing smoothing steps.

## The complete web JS pipeline (single source of truth)

The web JS pipeline in `product/web/js/main.js` lines 228–256 and `product/web/js/pipeline.js`:

```
Step 1: computeKeepIndices(lap_time, lap_dist, start, end, trackLen)
        → drops boundary-artifact frames where lap_time_s < 0.5s
          AND lap_distance_m > trackLen / 2
        → product/web/js/pipeline.js line 192

Step 2: smoothLapTime(lap_time, keepIndices)
        → linearly interpolates across lap_time_s plateaus
        → walks through values; when consecutive are equal,
          interpolates from plateau start to next distinct value
        → product/web/js/pipeline.js line 214
        → Comment: "LMU's mCurrentET updates at scoring rate (~5 Hz, 200 ms
          quantum), so a 50 Hz recorder sees plateaus of identical
          lap_time_s values"

Step 3: resample(distances, smoothedLapTime, maxDist)
        → onto 1 m grid via linear interpolation
        → product/web/js/pipeline.js line 160

Step 4: forward-clamp
        → ensure lap_time_s is non-decreasing
        → product/web/js/main.js lines 245-249

Step 5: computeDeltaT(sessionLapTime, refLapTime)
        → dt[i] = sessionLapTime[i] - refLapTime[i]
        → product/web/js/pipeline.js line 182

Step 6: smoothDt(dt, maxRadius=20)
        → 41-bin (±20m) symmetric moving average
        → kernel shrinks toward boundaries (radius = min(maxRadius, i, n-1-i))
        → endpoint values preserved exactly
        → attenuates plateau-alignment jitter by ~6×
        → product/web/js/pipeline.js line 243
        → Comment: "Even after smoothLapTime, two laps' clock ticks land
          at slightly different distances (1-2 frames of recorder phase),
          so each tick boundary introduces up to ~20 ms of
          plateau-alignment jitter into Δt. The jitter has spatial
          period equal to the plateau length (~7 m at racing speed),
          so a 41-bin boxcar (±20 m) attenuates it by ~6× while
          preserving features at the scale of corners (typically
          50-100 m)."
```

## Proposals

### Option A: Node.js script as golden source

Create a standalone Node.js script (`dev/scripts/compute_delta_t.js`) that:
1. Takes pre-extracted Parquet columns as JSON input on stdin
2. Imports `resample`, `computeDeltaT`, `smoothDt`, `smoothLapTime`, `computeKeepIndices` from `product/web/js/pipeline.js`
3. Outputs the delta-t array as JSON on stdout
4. Python prepares the data, pipes it to Node.js, reads the result

**Pros:** Guaranteed identical results — literally the same code. No drift possible.
**Cons:** Requires Node.js at Python runtime. IPC overhead per lap comparison.

### Option B: Python ports ALL steps, with contract test

Port every missing step into Python and add a **contract test** that verifies both produce the same output:

1. `compute_keep_indices()` → drop boundary-artifact frames
2. `smooth_lap_time()` → interpolate across plateaus
3. `smooth_dt()` → 41-bin symmetric moving average with boundary shrinking

**Pros:** No runtime coupling. Python stays self-contained. Easier on Windows.
**Cons:** Two implementations. Drift risk — contract test catches it but doesn't prevent it.

### Option C: Shared JS module callable from Python

Same as Option A but the JS module takes data on stdin, not Parquet files.

**Pros:** Single source of truth. No Parquet dependency in JS.
**Cons:** Still requires Node.js at runtime.

## Recommendation

**Option B for now, with Option A as the long-term goal.**

Rationale:
- The Python coaching pipeline must run on Windows alongside LMU. Adding a Node.js subprocess dependency is doable (Node is already installed for the build), but Option B is simpler and faster.
- The contract test is the critical safety net — it catches drift immediately.
- If drift proves to be a recurring problem, migrate to Option A or C.

### Implementation steps for Option B

1. **Port `smooth_lap_time()` to Python** — see `product/web/js/pipeline.js` line 214:
   - Walk through sorted values with their keep-indices
   - When consecutive values are equal (plateau), linearly interpolate from plateau start to next distinct value
   - Trailing plateau at the end → leave flat (sub-200ms tail)

2. **Port `compute_keep_indices()` to Python** — see `product/web/js/pipeline.js` line 192:
   - Filter out frames where `lap_time_s < 0.5s` AND `lap_distance_m > trackLen / 2`
   - These are boundary-artifact frames that slipped through

3. **Port `smooth_dt()` to Python** — see `product/web/js/pipeline.js` line 243:
   - For each index i: radius = min(maxRadius, i, n-1-i)
   - Average all values in [i-radius, i+radius]
   - Symmetric kernel, boundary values preserved exactly

4. **Wire into `compare_laps()`** in the same order as the web JS:
   ```python
   keep = compute_keep_indices(current_lap_times, current_dist, 0, track_length, track_length)
   smoothed = smooth_lap_time(current_lap_times, keep)
   driver_lap_time_grid = resample_column(current_dist, smoothed, track_length)
   forward_clamp(driver_lap_time_grid)
   # same for ref
   delta_t_raw = compute_delta_time_trace(driver_lap_time_grid, ref_lap_time_grid)
   delta_t = smooth_dt(delta_t_raw, max_radius=20)
   ```

5. **Add a contract test** — test script that computes delta-t both ways and asserts match.

## Acceptance criteria

- Python delta-t values match web JS values on the Barcelona fixture (within 0.1ms per bin).
- `smooth_dt` with `max_radius=20` applied to the raw delta-t trace.
- `smooth_lap_time` applied before resampling (plateau interpolation).
- `compute_keep_indices` filters boundary-artifact frames.
- All existing tests pass.
- Contract test passes.