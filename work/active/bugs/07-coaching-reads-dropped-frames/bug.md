# Bug 07: Coaching compares against incomplete live frame buffer — ✅ FIXED

## Reference data (in this folder)

| File | Description |
|---|---|
| `driver_lap14_paul-ricard---3a_session20260525.parquet` | Lap 14 extracted from the recorded session (3935 frames — complete) |
| `reference_paul-ricard---3a_dkr-engineering-4-elms25_time_01.19.010.parquet` | Reference lap used by both compare.html and the coaching pipeline |

To reproduce the discrepancy, run `compare_laps` on the driver file above against
the reference file, then compare the output to what the coaching pipeline reported
at the time.

## Observed discrepancy

**Coaching utterance (live, lap 14):**
> "Lost over three seconds at turn one exit. Gained time at turn two entry, lifted earlier."

**compare_laps on full session Parquet (3935 frames):**
```
lap_time_delta = -0.371 s   (driver was 0.37 s FASTER than reference)

Top losses:
  turn 1  exit_brake     loss= 0.235 s   driver=65.1 km/h   ref=66.7 km/h
  turn 4  minimum_speed  loss= 0.187 s   driver=124.3 km/h  ref=139.0 km/h
  turn 1  exit_throttle  loss= 0.152 s   driver=74.7 km/h   ref=85.6 km/h

Top gains:
  turn 2  minimum_speed  loss=-0.285 s   driver=121.8 km/h  ref=111.4 km/h
  turn 2  exit           loss=-0.248 s   driver=122.9 km/h  ref=114.0 km/h
  turn 5  exit_brake     loss=-0.189 s   driver=130.0 km/h  ref=119.8 km/h
```

**compare.html (same session Parquet, lap 14 vs reference):**
- T1: 41 ms loss
- T2 exit → T3 entry: 421 ms gain

The coaching pipeline reported "over three seconds" at T1. The actual loss was
**0.235 s** — a 13× exaggeration. The driver was overall 0.37 s faster than
the reference, which the coach did not mention at all.

## Root cause

The `QueuedBus` has `maxsize=256`. The bus has a single worker thread.
That same worker thread runs `_on_frame` (fast) but also runs
`_on_lap_completed` (slow: JS pipeline subprocess + LLM network call,
typically 5–15 s total).

While `_on_lap_completed` is blocked waiting for the LLM response, the
recorder is publishing at 50 Hz into the 256-slot queue. At 50 Hz, the
queue saturates in ~5 s. After that, `QueuedBus.publish` drops the oldest
frame to make room for the newest one.

**Frame count evidence:**
```
coach: lap completed: lap 14, frames=3093   ← from LapCompleted.frames (bus)
session parquet lap 14:         3935 frames  ← written by SessionWriter (complete)
delta:                           842 frames dropped  (21% of the lap)
```

842 frames were silently dropped from the live buffer. The dropped frames are
concentrated in whatever part of the lap coincided with the previous lap's
5–15 s LLM call window. This creates systematic gaps in `lap_time_s`, which
distort the JS pipeline's `smoothLapTime` and delta-t computation, producing
inflated loss values in random corners.

## Why compare.html is correct

compare.html reads the recorded session Parquet written by `SessionWriter`,
which runs on a dedicated shard-flush thread independent of the bus. It
receives every frame and is never affected by queue pressure.

## Fix direction

**See [`design-options.md`](design-options.md) for three architectural options, test plans, and recommendation.**

The minimum fix (Option A) is to move `_on_lap_completed` and `_on_corner_exited` off the bus worker thread onto a `ThreadPoolExecutor`. The end state (Option C) is to read after-lap data from the session Parquet instead of the bus buffer. See the design doc for full details.

## Files

- `product/python/lap_telemetry/coach/coach_tap.py` — `_on_lap_completed` and `_on_corner_exited` should submit work to a thread pool, not run inline
- `product/python/lap_telemetry/coach/live_fact_generator.py` — the `generate()` call blocks the worker
- `product/python/lap_telemetry/recorder/bus.py` — `QueuedBus` drops oldest when full
- `product/python/lap_telemetry/recorder/record.py` — recorder loop that publishes frames
- `product/python/lap_telemetry/recorder/writer.py` — `SessionWriter`, needs a lap-flush notification hook for Options B and C
