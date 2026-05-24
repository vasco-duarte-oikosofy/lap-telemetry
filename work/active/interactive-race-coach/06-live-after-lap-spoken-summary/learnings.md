# Slice 06: Live After-Lap Spoken Summary — Learnings

## 1. Track name matching requires prefix-style resolution

LMU track names (e.g. "Circuit de Barcelona-Catalunya") don't always exactly
match the slug in reference/model filenames (e.g. "circuit-de-barcelona").
The resolvers use a flexible prefix match: if the live slug starts with the
file's track prefix (followed by `-`), it's a match. This handles the common
case where LMU appends "-Catalunya" or similar qualifiers that the session
file doesn't include.

## 2. PyArrow `pa.table()` triggers pandas import on some systems

In conda environments with numpy 2.x and an older pandas (2.0.3), `pa.table()`
triggers a pandas import which crashes with `numpy.dtype size changed`. The
fix is upgrading pandas (`pip install --upgrade pandas`). This is an
environment issue, not a code bug. The `pa.table()` call with an explicit
schema works fine — the crash is triggered by the pandas path inside pyarrow's
type inference, which isn't used when we provide `_SCHEMA`.

## 3. `frames_to_parquet` reuses `SessionWriter._SCHEMA`

The Frame→Parquet bridge reuses `_SCHEMA` from `writer.py` to ensure column
names and types exactly match what `compare_laps()` expects. This means a
dependency on the recorder's writer module, but it avoids schema drift.

## 4. `compare_laps()` can handle partial laps (but results may be odd)

The comparison engine works on completed-lap data that may only cover a
fraction of the track. When fed a partial lap (e.g. 50 frames at 0–490m),
it produces results, but the delta-t computation may be unreliable. This is
acceptable for the coach — an incomplete comparison is better than silence,
and the driver will get better coaching on the next full lap.

## 5. SpeechQueue + FileAdapter is reliable for testing

Using `FileAdapter` (which writes text to a file) with `SpeechQueue` is an
effective way to test the full pipeline without needing Kokoro or speakers.
The `flush()` call blocks until the queued utterance is written, making
assertions deterministic.

## 6. Temp Parquet files must be cleaned up after comparison

`frames_to_parquet()` creates temp files in `/tmp`. The caller
(`LiveFactGenerator.generate()`) is responsible for deleting them. The
`try/finally` block ensures cleanup even if `compare_laps()` raises.

## 7. CoachTap's `_on_lap_completed` runs on the QueuedBus worker thread

This is by design — the bus worker thread processes frames and calls
subscribers. The fact generation, LLM call, and TTS all happen off the
50 Hz recorder thread. The `SpeechQueue` has its own worker thread for
TTS synthesis, so the bus worker is only blocked during fact generation
and LLM call, not during audio playback.