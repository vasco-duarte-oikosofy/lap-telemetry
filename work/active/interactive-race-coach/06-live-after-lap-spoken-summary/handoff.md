# Slice 06: Live After-Lap Spoken Summary — Handoff

## What is on disk

### New files
- `product/python/lap_telemetry/coach/reference_resolver.py` — Resolves track names to reference lap Parquet files with flexible prefix matching and caching
- `product/python/lap_telemetry/coach/track_model_resolver.py` — Resolves track names to track coaching model JSON files with flexible prefix matching and caching
- `product/python/lap_telemetry/coach/frames_to_parquet.py` — Converts `list[Frame]` to a temporary Parquet file using `SessionWriter._SCHEMA`
- `product/python/lap_telemetry/coach/live_fact_generator.py` — `LiveFactGenerator` class: receives `LapCompleted`, resolves ref/model, converts to Parquet, runs `compare_laps()`, generates utterance via LLM
- `dev/scripts/test_live_after_lap_spoken_summary.py` — Python test (40 assertions)
- `dev/scripts/test_live_after_lap_spoken_summary.js` — Node.js wrapper for parallel runner

### Modified files
- `product/python/lap_telemetry/coach/coach_tap.py` — Enhanced to accept `LiveFactGenerator` and `SpeechQueue`; on `LapCompleted`, calls fact generator and enqueues utterance
- `product/python/lap_telemetry/coach/live_coach.py` — Full CLI with `--tts-engine`, `--tts-output`, `--config`, `--debug` flags; wires bus → detector → fact gen → LLM → TTS
- `record_with_coach.py` — Updated to use `live_coach.main()` (which now includes TTS)
- `package.json` — Added `dev/scripts/test_live_after_lap_spoken_summary.js` to `interactive-race-coach` feature tests

## Pipeline architecture

```
Recorder (50 Hz loop)
   │
   ├─→ SessionWriter (Parquet — unchanged)
   │
   └─→ QueuedBus (worker thread)
         │
         └─→ LapDetector (on bus worker thread)
               │
               ├─ NewLap event → debug print only
               │
               └─ LapCompleted event (carries frozen frames)
                     │
                     └─→ LiveFactGenerator.generate()
                           │ resolves reference lap + track model
                           │ converts frames to temp Parquet
                           │ calls compare_laps()
                           │ calls LLM via utterance_fn
                           │
                           └─→ SpeechQueue.enqueue(utterance)
                                 │ (separate worker thread)
                                 └─→ TTS adapter → speaker
```

## Feature flags / config
- Bus is opt-in: `bus=None` (default in `record.run()`) means zero overhead
- TTS engine configurable via `--tts-engine kokoro|pyttsx3|file` or `COACH_TTS_ENGINE` env var
- LLM config via `coach_config.toml` or `--config`
- Reference/model resolution caches per process; `_cache={}` enables caching

## New helpers worth knowing
- `resolve_reference_lap(track_name, search_dir, _cache)` — flexible prefix-match resolver
- `resolve_track_model(track_name, search_dir, _cache)` — same pattern for track models
- `frames_to_parquet(frames)` → `Path` — temp file, caller must `unlink()`
- `LiveFactGenerator(utterance_fn, config)` → call `.generate(LapCompleted)` → `str | None`
- `CoachTap(bus, fact_generator, speech_queue)` — enhanced orchestrator

## Deferred TODOs
- Speech window detection (find a straight before speaking) — slice 07
- Corner-exit coaching (mid-lap utterances) — slice 07
- Refactor `compare_laps()` to accept in-memory data (avoid temp Parquet bridge)
- Fuel/race-state channels in Frame — slice 08+

## Runtime notes
- `python3 record_with_coach.py --out-dir sessions` starts the full pipeline
- Use `--tts-engine file --tts-output /tmp/coach.txt` for testing without speakers
- Use `--debug` for verbose logging of fact generation timing and LLM I/O
- If no reference or model exists for a track, a warning is printed to stderr and no utterance is generated

## Test status
- All 40 assertions pass in `test_live_after_lap_spoken_summary.py`
- Feature test suite (`interactive-race-coach`) passes — 2 pre-existing failures are unrelated (delta_time, track_model tests)
- `npm run build` succeeds