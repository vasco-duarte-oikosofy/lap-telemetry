# Handoff — Slice 04: Local TTS Smoke Path

## State on disk

### New files
- `product/python/lap_telemetry/coach/tts_adapter.py` — TTSAdapter ABC + PiperAdapter, Pyttsx3Adapter, FileAdapter, create_adapter() factory
- `product/python/lap_telemetry/coach/speech_queue.py` — SpeechQueue with non-blocking enqueue, stale dropping, flush, shutdown
- `product/python/lap_telemetry/coach/speak.py` — CLI entry point (`python -m lap_telemetry.coach.speak --text "..."`)
- `product/python/demo_coach_slice04.py` — Demo script for end-to-end TTS
- `dev/scripts/test_local_tts_smoke_path.js` — 15 unit + CLI tests

### Modified files
- `product/python/lap_telemetry/coach/coach_config.py` — Added TTSConfig dataclass, load_tts_config(), refactored _read_toml to support multiple sections
- `coach_config.toml` — Added [tts] section
- `package.json` — Added `local-tts-smoke-path` feature test suite
- `dev/scripts/test_llm_text_adapter.js` — Fixed pre-existing max_tokens assertion (100→4096)

## Feature flags / config

- `[tts]` section in `coach_config.toml`:
  - `engine`: "piper" | "pyttsx3" | "file" (default: "piper")
  - `piper_binary`: path to piper executable (default: "piper")
  - `piper_model`: path to .onnx voice model (no default — must be set for Piper)
  - `output_file`: output path for FileAdapter (default: "coach_output.wav")
- Env var overrides: `COACH_TTS_ENGINE`, `COACH_PIPER_BINARY`, `COACH_PIPER_MODEL`, `COACH_TTS_OUTPUT_FILE`

## New helpers

- `create_adapter(config: TTSConfig) -> TTSAdapter` — factory to create the right adapter
- `SpeechQueue(adapter, maxsize=2)` — non-blocking queue with stale drop
- `load_tts_config(config_path) -> TTSConfig` — load TTS section from TOML + env overrides

## Deferred TODOs

- Piper is not installed on this machine — PiperAdapter._synthesize() and _play_wav() are untested with real Piper. Manual smoke test needed after installing Piper + voice model.
- pyttsx3 is not installed — Pyttsx3Adapter not tested on this machine (Windows-only)
- sounddevice is not installed — PiperAdapter falls back to platform audio player
- Volume/output-device configuration (out of scope)
- Voice selection beyond one default voice (out of scope)

## PowerShell smoke command (for Windows validation)

```powershell
python -m lap_telemetry.coach.speak --text "Lost time in turn 3 exit"
```

## Test commands

```bash
bash scripts/test-summary.sh --feature local-tts-smoke-path    # feature tests (8 scripts, 183 assertions)
bash scripts/test-summary.sh                                    # full suite (50 scripts, 1224 assertions)
```