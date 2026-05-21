# Fix: Delta-T calculation must use the exact same code as the web UI

## Problem

The Python coaching facts code (`lap_comparator.py`) and the web UI (`product/dist/compare.html`) compute delta-t independently. They currently produce **different results** because:

1. **Missing `smoothLapTime()` step.** The web JS linearly interpolates across `lap_time_s` plateaus *before* resampling (see `product/web/js/pipeline.js` line 214). Our Python code resamples raw `lap_time_s` without plateau smoothing.

2. **Missing `smoothDt()` step.** The web JS applies a 41-bin (±20m) symmetric moving average to the raw delta-t to suppress plateau-alignment jitter (see `product/web/js/pipeline.js` line 243 with detailed comments on lines 237–242). Our Python code uses the raw delta-t.

3. **Missing `computeKeepIndices()`.** The web JS drops boundary-artifact frames before resampling (frames where `lap_time_s < 0.5s` and `lap_distance_m > trackLen / 2`). Our Python code doesn't filter these.

The result: when you read delta-t at 2158m on the web UI and in the coaching facts, you get different values. The coaching facts must match the web UI exactly so that coaching messages are consistent with what the driver sees on screen.

## The web JS pipeline (single source of truth)

The complete delta-t pipeline in the web JS (`product/web/js/main.js` lines 228–256 and `product/web/js/pipeline.js`):

```
Step 1: computeKeepIndices(lap_time, lap_dist, start, end, trackLen)
        → drops boundary-artifact frames
        
Step 2: smoothLapTime(lap_time, keepIndices)
        → linearly interpolates across lap_time_s plateaus
        
Step 3: resample(distances, smoothedLapTime, maxDist)
        → onto 1 m grid via linear interpolation
        
Step 4: forward-clamp
        → ensure lap_time_s is non-decreasing
        
Step 5: computeDeltaT(sessionLapTime, refLapTime)
        → dt[i] = sessionLapTime[i] - refLapTime[i]
        
Step 6: smoothDt(dt, maxRadius=20)
        → symmetric moving average (±20m) to suppress jitter
```

## Proposals

### Option A: Node.js script as golden source

Create a standalone Node.js script (`dev/scripts/compute_delta_t.js`) that:
1. Reads two Parquet files (driver + reference)
2. Imports `resample`, `computeDeltaT`, `smoothDt`, `smoothLapTime`, `computeKeepIndices` from `product/web/js/pipeline.js`
3. Outputs the delta-t trace as a JSON array (1 value per meter)
4. Python calls this via `subprocess` and loads the result

**Pros:** Guaranteed identical results — literally the same code. No drift possible.
**Cons:** Adds a Node.js runtime dependency to the Python coaching pipeline. Slower (subprocess call). Need to handle Parquet reading in Node.js (currently JS reads from pre-loaded data, not directly from Parquet).

**Practical concern:** The web JS currently reads from the in-memory data store, not from Parquet files. We'd need to add Parquet reading (e.g., via `apache-arrow` npm package) or pre-process the data into a format the JS can consume.

### Option B: Python ports ALL steps, with contract test

Port every step of the web JS pipeline into Python:
1. `compute_keep_indices()` → drop boundary-artifact frames
2. `smooth_lap_time()` → interpolate across plateaus
3. `resample_column()` → already exists ✅
4. `forward_clamp()` → already exists ✅
5. `compute_delta_time_trace()` → already exists ✅
6. `smooth_dt()` → new, 41-bin symmetric moving average

Add a **contract test** that runs both the JS and Python on the same input data and asserts the outputs match within a tight tolerance (e.g. < 0.1ms per bin).

**Pros:** No runtime coupling. Python pipeline stays self-contained. Easier to run on Windows.
**Cons:** Two implementations to maintain. Drift risk — the contract test catches it but doesn't prevent it.

### Option C: Shared computation module (JS, callable from Python)

Extract the delta-t computation into a standalone JS module that:
1. Takes pre-extracted Parquet columns as JSON input on stdin
2. Runs the full pipeline (steps 1–6)
3. Outputs the delta-t array as JSON on stdout

Python prepares the data, pipes it to Node.js, reads the result.

**Pros:** Single source of truth. No Parquet dependency in JS.
**Cons:** Still requires Node.js at runtime. IPC overhead per lap comparison.

## Recommendation

**Option B for now, with Option A as the long-term goal.**

Rationale:
- The Python coaching pipeline must run on Windows alongside LMU. Adding a Node.js subprocess dependency is doable (Node is already installed for the build), but Option B is simpler and faster.
- The contract test is the critical safety net — it catches drift immediately.
- If drift proves to be a recurring problem, migrate to Option A or C.

### Implementation steps for Option B

1. **Port `smooth_lap_time()` to Python** — linearly interpolate across `lap_time_s` plateaus before resampling. See `product/web/js/pipeline.js` line 214 for the exact algorithm: walk through sorted values, when consecutive values are equal, linearly interpolate from the plateau start to the next distinct value.

2. **Port `compute_keep_indices()` to Python** — filter out boundary-artifact frames where `lap_time_s < 0.5s` and `lap_distance_m > trackLen / 2`. See `product/web/js/pipeline.js` line 192.

3. **Port `smooth_dt()` to Python** — 41-bin symmetric moving average with boundary radius shrinking. See `product/web/js/pipeline.js` line 243 and the detailed comment above it (lines 237–242).

4. **Wire these into `compare_laps()`** — call them in the same order as the web JS:
   ```
   keep = compute_keep_indices(current_lap_times, current_dist, 0, track_length, track_length)
   smoothed = smooth_lap_time(current_lap_times, keep)
   driver_lap_time_grid = resample_column(current_dist, smoothed, track_length)
   forward_clamp(driver_lap_time_grid)
   # same for ref
   delta_t_raw = compute_delta_time_trace(driver_lap_time_grid, ref_lap_time_grid)
   delta_t = smooth_dt(delta_t_raw, max_radius=20)
   ```

5. **Add a contract test** — a test script that:
   - Computes delta-t using the Python pipeline
   - Computes delta-t using the Node.js pipeline (via `product/web/js/pipeline.js`)
   - Asserts they match within tolerance on the Barcelona fixture
   - Run as part of the test suite

### What this fixes

Currently, delta-t at 2158m from Python (after switching to lap_time_s) = +423.5ms. The web UI likely shows a different value because it applies `smoothLapTime` and `smoothDt`. After matching the full pipeline, both should produce identical values.

## Files to modify

- `product/python/lap_telemetry/coach/lap_comparator.py` — add `smooth_lap_time()`, `compute_keep_indices()`, `smooth_dt()`, wire into `compare_laps()`
- `dev/scripts/test_phase_detection.py` — update tests
- `dev/scripts/test_delta_t_contract.py` (new) — contract test comparing Python vs JS output

## Acceptance criteria

- Python delta-t values match web JS values on the Barcelona fixture (within 0.1ms per bin).
- `smooth_dt` with `max_radius=20` applied to the raw delta-t trace.
- `smooth_lap_time` applied before resampling (plateau interpolation).
- `compute_keep_indices` filters boundary-artifact frames.
- All existing tests pass.
- Contract test passes.