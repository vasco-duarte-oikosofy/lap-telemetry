# Handoff — Slice 04: Local TTS Smoke Path

## State on disk

### New files
- `product/python/lap_telemetry/coach/tts_adapter.py` — TTSAdapter ABC + KokoroAdapter (primary), PiperAdapter, Pyttsx3Adapter, FileAdapter
- `product/python/lap_telemetry/coach/speech_queue.py` — SpeechQueue with non-blocking enqueue, stale dropping, flush, shutdown
- `product/python/lap_telemetry/coach/speak.py` — CLI entry point (`python -m lap_telemetry.coach.speak --text "..."`)
- `product/python/demo_coach_slice04.py` — Demo script for end-to-end TTS
- `dev/scripts/test_local_tts_smoke_path.js` — 16 unit + CLI tests
- `docs/PIPER_INSTALL.md` — Install instructions for Kokoro (primary) and Piper (secondary)
- `product/data/tts-voices/` — Kokoro model + voices, Piper voices (gitignored)
- `work/active/interactive-race-coach/04-local-tts-smoke-path/04b.1-find-model-that-speaks-naturally/` — Sub-slice for voice quality evaluation

### Modified files
- `product/python/lap_telemetry/coach/coach_config.py` — TTSConfig now includes kokoro_model, kokoro_voices, kokoro_voice, kokoro_speed; default engine changed to "kokoro"
- `coach_config.toml` — `[tts]` section now uses Kokoro with bm_daniel
- `package.json` — `local-tts-smoke-path` feature test suite
- `dev/scripts/test_llm_text_adapter.js` — Fixed pre-existing max_tokens assertion (100→4096)

## Feature flags / config

- `[tts]` section in `coach_config.toml`:
  - `engine`: "kokoro" | "piper" | "pyttsx3" | "file" (default: "kokoro")
  - `kokoro_model`: path to ONNX model (default: `product/data/tts-voices/kokoro-v1.0.int8.onnx`)
  - `kokoro_voices`: path to voices bin (default: `product/data/tts-voices/kokoro-voices-v1.0.bin`)
  - `kokoro_voice`: voice name (default: "bm_daniel" — British male, race engineer feel)
  - `kokoro_speed`: speaking speed (default: 1.05 — slightly faster than normal)
  - `piper_binary`: path to piper executable (default: "python3 -m piper")
  - `piper_model`: path to .onnx voice model
  - `output_file`: output path for FileAdapter (default: "coach_output.wav")
- Env var overrides: `COACH_TTS_ENGINE`, `COACH_KOKORO_MODEL`, `COACH_KOKORO_VOICES`, `COACH_KOKORO_VOICE`, `COACH_PIPER_BINARY`, `COACH_PIPER_MODEL`, `COACH_TTS_OUTPUT_FILE`

## New helpers

- `KokoroAdapter(config)` — primary TTS engine, lazy-loads Kokoro ONNX model
- `create_adapter(config)` — factory now supports "kokoro" engine
- `load_tts_config()` — loads TTS config with Kokoro fields
- `SpeechQueue(adapter)` — non-blocking queue with stale drop

## Voice quality

Current voice (bm_daniel via Kokoro) is "ok-ish" — better than Piper's
robotic output but still not fully natural. Sub-slice 04b.1 continues
evaluation of ChatTTS, Qwen3-TTS, and XTTS-v2 for better intonation.

## Deferred TODOs

- Voice quality evaluation (sub-slice 04b.1)
- pyttsx3 is not installed — Pyttsx3Adapter not tested (Windows-only)
- Volume/output-device configuration (out of scope)
- Voice selection beyond one default voice (out of scope)
- Text preprocessing for abbreviations ("4m" → "4 meters") — noted in 04b.1 prompt

## PowerShell smoke command (for Windows validation)

```powershell
python -m lap_telemetry.coach.speak --text "Box this lap, box this lap. Medium tyre."
```

## Test commands

```bash
bash scripts/test-summary.sh --feature local-tts-smoke-path    # feature tests (8 scripts, 183+ assertions)
bash scripts/test-summary.sh                                    # full suite (50 scripts, 1224 assertions)
```