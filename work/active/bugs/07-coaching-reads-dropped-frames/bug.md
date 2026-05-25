# Bug 07: Coaching compares against incomplete live frame buffer

## Observed

Coaching utterance for lap 14: "Lost over three seconds at turn one exit."

Running `compare_laps` on the same lap from the session Parquet produces
T1 exit loss of **0.235 s** — not 3 seconds. compare.html agrees: 41 ms
at T1. The coaching output is completely wrong.

## Root cause

The `QueuedBus` has `maxsize=256`. The bus has a single worker thread.
That same worker thread runs `_on_frame` (fast) but also runs
`_on_lap_completed` (slow: JS pipeline subprocess + LLM network call,
typically 5–15 s total).

While `_on_lap_completed` is blocked waiting for the LLM response, the
recorder is publishing at 50 Hz into the 256-slot queue. At 50 Hz, the
queue saturates in ~5 s. After that, `QueuedBus.publish` drops the oldest
frame to make room for the newest one.

**Evidence:**
```
coach: lap completed: lap 14, frames=3093   ← from LapCompleted.frames
session parquet lap 14: 3935 frames         ← written by SessionWriter
```
842 frames were silently dropped — 21 % of the lap. The dropped frames
are distributed non-uniformly (they are the frames that arrived while the
previous lap's LLM call was in flight), which distorts the `lap_time_s`
timeline. The JS pipeline's `smoothLapTime` and delta-t computation then
produce a garbage trace, and `compare_laps` reports inflated losses.

## Why compare.html is correct

compare.html reads the recorded session Parquet written by `SessionWriter`,
which runs on a dedicated shard-flush thread and is never affected by bus
queue pressure. It has every frame.

## Fix direction

Do **not** do the JS pipeline + LLM call on the bus worker thread.
After `LapCompleted` fires, hand off the heavy work to a separate
`ThreadPoolExecutor` so the bus worker is free to continue draining
frames. The `LapCompleted.frames` itself would still be the bus-delivered
frames (with potential drops), so the deeper fix (bug 08) is to read
from the session Parquet instead.

## Files

- `product/python/lap_telemetry/coach/coach_tap.py` — `_on_lap_completed`
  should submit work to a thread pool, not run inline
- `product/python/lap_telemetry/coach/live_fact_generator.py` — the
  `generate()` call blocks the worker
