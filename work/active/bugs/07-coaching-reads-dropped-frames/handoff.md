# Bug 07 Handoff

## Status: ✅ Fixed

## What is on disk

### Changed files
- **`product/python/lap_telemetry/coach/coach_tap.py`** — Complete rewrite:
  - Added `ThreadPoolExecutor(max_workers=1)` for analysis (Option A).
  - Added `notify_parquet_flushed()` method and `_wait_for_parquet()` for dual-path (Option C).
  - `_on_lap_completed` now submits `_analyze_lap` to the pool (non-blocking for bus worker).
  - `_on_corner_exited` now submits `_analyze_corner` to the pool.
  - `_analyze_lap` tries Parquet path first, falls back to `event.frames` on timeout.
  - `_analyze_corner` uses live frames from `LapDetector.current_lap_frames`.
  - Fuel fact generation preserved in `_analyze_lap` (runs after main utterance).
  - `shutdown()` waits for pool to complete before returning.

- **`product/python/lap_telemetry/recorder/writer.py`** — Added `on_lap_flushed` callback:
  - `SessionWriter.__init__()` accepts `on_lap_flushed: Callable[[Path, int], None] | None`.
  - Tracks lap boundaries in `append()` via `_prev_lap_number` and `_completed_lap_numbers`.
  - `flush_shard()` fires the callback for each completed lap number.

- **`product/python/lap_telemetry/recorder/bus.py`** — Added `on_lap_flushed` attribute to `QueuedBus`:
  - `QueuedBus.on_lap_flushed` defaults to `None`, set by the wiring layer.

- **`product/python/lap_telemetry/recorder/record.py`** — Wires callback:
  - When creating `SessionWriter`, passes `bus.on_lap_flushed` as the callback (if set).

- **`product/python/lap_telemetry/coach/live_coach.py`** — Wires tap to bus:
  - `bus.on_lap_flushed = tap.notify_parquet_flushed`

- **`product/python/lap_telemetry/coach/live_fact_generator.py`** — Added `generate_from_parquet()`:
  - Reads a specific lap from a session Parquet file instead of converting `event.frames`.
  - Resolves reference/model, calls `compare_laps()` with `lap_number=` filter.

- **`product/python/lap_telemetry/coach/lap_comparator.py`** — Added `lap_number` parameter:
  - `compare_laps()` accepts optional `lap_number: int | None`.
  - When set, filters `current_table` to only rows matching that lap number.

- **`dev/scripts/test_live_after_lap_spoken_summary.py`** — Updated T14:
  - Sets `COACH_PARQUET_TIMEOUT_S=0.01` for fast fallback.
  - Drains the thread pool before asserting utterances.

### New files
- **`dev/scripts/test_nonblocking_coach_pipeline.py`** — 46 assertions covering Options A+B+C.
- **`dev/scripts/test_nonblocking_coach_pipeline.js`** — JS wrapper for parallel test runner.

### Updated files
- **`package.json`** — Added `bug07-nonblocking-coach` feature test list.

## Feature flags / configuration

- `COACH_PARQUET_TIMEOUT_S` env var — controls how long `_wait_for_parquet()` waits before falling back to `event.frames`. Default: 10.0 seconds. Set to 0.01 in tests for fast fallback.

## How the fix works

### Before (bug)
```
recorder → bus.publish(frame) → QueuedBus worker thread
                                     ├── LapDetector._on_frame() (fast, ~0.2ms)
                                     └── _on_lap_completed() (SLOW: 5-50s)
                                              → queue fills up → drops oldest frames
```

### After (Option C: dual-path)
```
recorder → bus.publish(frame) → QueuedBus worker thread (never blocks)
                                     └── LapDetector._on_frame() (~0.2ms)
                                             └── submit to ThreadPoolExecutor
                                                     ├── _analyze_lap()
                                                     │    ├── wait for SessionWriter flush
                                                     │    ├── read session Parquet (complete data)
                                                     │    ├── compare_laps(lap_number=N)
                                                     │    └── utterance_fn()
                                                     └── _analyze_corner()
                                                          ├── use live frames (LapDetector buffer)
                                                          └── utterance_fn()

recorder → writer.append(frame) → SessionWriter (own memory, never drops)
                                     └── flush_shard() → on_lap_flushed(path, lap_number) → CoachTap
```

Key properties:
1. Bus worker thread never blocks — LapDetector.feed() is ~0.2ms per frame.
2. After-lap data comes from the session Parquet (authoritative, complete).
3. Corner-exit data comes from live buffer (fast, small window, ~150m).
4. Both analyses run on the pool thread (max_workers=1 for serialization).
5. If the Parquet flush doesn't arrive within 10s, falls back to `event.frames`.

## Running the tests

```bash
bash scripts/test-summary.sh --feature bug07-nonblocking-coach
```

46 assertions covering: thread pool creation, non-blocking bus, parquet flush callback, lap_number filter, generate_from_parquet, dual-path wiring, shutdown behavior.