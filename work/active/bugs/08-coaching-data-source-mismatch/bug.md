# Bug 08: Coaching pipeline reads live frame buffer; compare.html reads full session Parquet

## The standing rule we're missing

**Any telemetry analysis done by the coaching pipeline must operate on the
same data that compare.html operates on.** If they diverge, the coaching
facts cannot be validated by the user — what the coach says and what the
UI shows will never agree.

## Current state

| | Data source | Frames (lap 14) |
|---|---|---|
| **compare.html** | `SessionWriter` → session Parquet (full) | 3935 |
| **Coaching pipeline** | `LapCompleted.frames` from bus (dropped) | 3093 |

The JS pipeline code is the **same** in both paths: `compute_delta_t.mjs`
imports directly from `product/web/js/pipeline.js`, the same file the
browser loads. The computation logic is shared. The *data* is not.

## Root cause

`LiveFactGenerator.generate()` calls `frames_to_parquet(event.frames)` to
produce a temp Parquet from the live bus frames, then runs `compare_laps()`
on that temp file. The live frames come from `LapCompleted.frames`, which
is populated by `LapDetector` from the `QueuedBus` worker thread — subject
to queue drops (see bug 07).

`SessionWriter` writes to the session Parquet independently, on its own
flush thread, from the same raw frame stream. It never drops frames.

## Fix direction

After a lap completes, instead of converting `event.frames` to a temp
Parquet, wait for `SessionWriter` to flush the completed lap to disk and
then pass the session Parquet path (plus the lap number) directly to
`compare_laps()`. The comparator already knows how to filter by lap
number (it uses `lap_number` from the Parquet).

This requires:
1. `SessionWriter` to signal (e.g. via a callback or event) when it has
   flushed a completed lap and which lap number it contains.
2. `LiveFactGenerator` to receive that path + lap number instead of raw frames.
3. `compare_laps()` to pre-filter to a specific lap number before passing
   to the JS pipeline (it currently reads the whole file).

Until that is done, all coaching comparisons are potentially operating on
incomplete data and cannot be trusted to match what compare.html shows.

## Files

- `product/python/lap_telemetry/coach/live_fact_generator.py` — data source
- `product/python/lap_telemetry/recorder/writer.py` — `SessionWriter`, needs
  a lap-flush notification hook
- `product/python/lap_telemetry/coach/lap_comparator.py` — needs
  lap-number pre-filter when reading full session Parquet
