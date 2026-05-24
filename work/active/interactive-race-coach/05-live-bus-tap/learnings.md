# Slice 05: Live Bus Tap — Learnings

## 1. Python tests need a Node.js wrapper for the parallel runner

The test runner (`run-tests-parallel.js`) discovers and executes `.js` files with `node`. A raw `.py` test is invisible to it. Following TESTING_LESSONS.md L12, create a thin `.js` wrapper that:
- Spawns `python3` with explicit `env: { ...process.env, PYTHONPATH }`
- Forwards stdout/stderr (which contain `[PASS]`/`[FAIL]` lines)
- Has its own `ok()` call with `[PASS]`/`[FAIL]` in source text (satisfies `test_protocol_enforcement.js`)
- Uses `// @parallel true` header

## 2. QueuedBus drop testing needs careful synchronization

Testing "oldest-first drop when full" requires the worker thread to be blocked while you fill the queue past capacity. Using `threading.Event` pairs (block_event / release_event) is more reliable than `threading.Barrier`, which can throw `BrokenBarrierError` if the test timing is off.

## 3. record.py pulls in pyarrow on import

`from lap_telemetry.recorder import record` transitively imports `writer.py` → `pyarrow`. In environments with numpy version mismatches, this crashes. Tests that only need `_is_recordable` or the function signature should use `ast.parse()` on the source file or test the function's logic inline (not via import).

## 4. LiveBus callback exception isolation is critical

If a subscriber callback raises, the LiveBus must catch it, log it, and continue calling remaining subscribers. Without this, a buggy coach subscriber would crash the 50 Hz recorder loop.

## 5. LapDetector emits events in the same call as feed()

Both `on_lap_completed` and `on_new_lap` fire synchronously inside `feed()`. This is by design — the LapDetector has no threads. When used via QueuedBus, the callbacks run on the bus worker thread, which is fine.

## 6. LapDetector edge case: backward lap number

When `lap_number` decreases (session restart), the in-progress lap is discarded without a `LapCompleted` event. This prevents spurious "completed" events for partial laps that were interrupted by a session reset. The detector only emits `LapCompleted` when the lap number increases (normal forward boundary).

## 7. QueuedBus drain on shutdown

After `shutdown()`, the worker drains any remaining items in the queue before exiting. This ensures no frames are lost on clean teardown, which matters for the lap detector seeing the final frames of a session.

## 8. `python -m lap_telemetry.coach.live_coach` needs PYTHONPATH

The package lives under `product/python/`, which isn't on the default `sys.path`. Users must either:
- Run `python3 record_with_coach.py` (which adds the path automatically), or
- Set `PYTHONPATH=product/python python3 -m lap_telemetry.coach.live_coach`

## 9. NumPy 2 / PyArrow 1.x incompatibility blocks recorder imports

In conda environments with NumPy 2.x and an older PyArrow, `import pyarrow` crashes with `AttributeError: _ARRAY_API not found`. Fix: `pip install --upgrade pyarrow` or use a venv with compatible versions. This is an environment issue, not a code bug.