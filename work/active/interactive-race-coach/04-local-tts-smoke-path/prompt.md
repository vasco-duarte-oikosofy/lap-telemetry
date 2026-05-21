# Slice 4: Local TTS Smoke Path

## Goal

Build a local TTS adapter that takes a text string and speaks it through
headphones, with queue semantics (non-blocking enqueue, worker thread
synthesis + playback, stale utterance dropping). This validates that audio
can be produced locally on Windows without blocking the recorder loop.

## Architecture risk validated

Can a local TTS engine produce audible coaching utterances on the same
machine that runs LMU, without blocking the 50 Hz recorder loop and without
requiring internet?

## User-visible result

CLI command that speaks a supplied text string through the default audio
output device:

```bash
python3 -m lap_telemetry.coach.speak \
  --text "Lost time in turn 3 exit — minimum speed 10 km/h lower, released brakes 4m later, got to throttle 9m later. Gained in turn 5 — apexed earlier, back to throttle 10m earlier."
```

Also a PowerShell smoke command documented for Windows validation.

## Scope

### In scope

1. **TTS adapter module** (`lap_telemetry/coach/tts_adapter.py`)
   - Abstract `TTSAdapter` base class with `speak(text)` method
   - `PiperAdapter` — calls Piper binary via subprocess (primary engine)
   - `Pyttsx3Adapter` — uses pyttsx3/SAPI as zero-install fallback (Windows-only)
   - `FileAdapter` — writes audio to a WAV file (for testing without speakers)
   - All adapters handle short utterances synchronously within their `speak()` call

2. **Speech queue** (`lap_telemetry/coach/speech_queue.py`)
   - Non-blocking `enqueue(text)` — adds utterance to a bounded queue
   - Worker thread dequeues, calls TTS adapter, plays audio
   - **Stale utterance dropping:** when a new utterance arrives while one is
    already queued or playing, the queued (not currently playing) utterance
    is dropped and replaced. The currently-playing utterance finishes.
   - `flush()` — blocks until the queue is empty and current playback finishes
   - `shutdown()` — stops the worker thread cleanly

3. **TTS configuration** (extend `coach_config.toml`)
   - Engine selection: `piper`, `pyttsx3`, `file`
   - Piper model path
   - Piper binary path
   - Output file path (for file adapter)
   - Config resolution: env vars override config file

4. **CLI entry point** (`speak`)
   - `--text` — the text to speak (required)
   - `--engine` — override TTS engine from config (`piper`, `pyttsx3`, `file`)
   - `--play` — play audio (default: true); with `--no-play` just synthesize to file
   - Prints confirmation to stdout, debug info to stderr

5. **Demo script** (`product/python/demo_coach_slice04.py`)
   - Speaks the default coaching phrase end-to-end
   - Similar pattern to `demo_coach_slice03.py`
   - Usage: `python3 demo_coach_slice04.py`
   - With custom text: `python3 demo_coach_slice04.py --text "your text here"`

### Out of scope

- Live telemetry integration (slice 5)
- LLM integration (already done in slice 3)
- Voice cloning, voice selection beyond one default voice
- Volume/output-device configuration
- Streaming/chunked audio (unnecessary for ≤35 word utterances)
- Cross-corner carry-over detection
- Race engineer calls (fuel, strategy)

## Default test phrase

The default phrase for testing throughout this slice:

> "Lost time in turn 3 exit — minimum speed 10 km/h lower, released brakes 4m later, got to throttle 9m later. Gained in turn 5 — apexed earlier, back to throttle 10m earlier."

This is the actual output from the LLM adapter in slice 03 with the
Barcelona canned facts. It is 27 words, well within the 35-word limit,
and exercises both loss and gain coaching points.

## TTS engine selection

### Primary: Piper

Rationale (from spec):
- Runs entirely offline on CPU alongside LMU without stealing resources.
- Same `.onnx` voice model produces identical audio on macOS and Windows.
- Sub-200 ms latency for ≤35 word utterances.
- Pre-built binaries available for both platforms.
- Simple invocation: `echo "text" | piper --model voice.onnx --output_file out.wav`

Piper invocation pattern:
```
piper --model <voice.onnx> --output_file <output.wav>
```
Text is piped via stdin. The binary produces a WAV file, which we then play
using `sounddevice` or `simpleaudio` (Python audio playback).

### Fallback: pyttsx3 / SAPI

Zero-install Windows fallback if Piper is not installed. Uses the Windows
SAPI voices. Sounds robotic but works everywhere Windows does.

### Testing-only: FileAdapter

Writes synthesized audio to a WAV file without playing it. Used in CI and
automated tests where no audio device is available. Also useful for
validating that synthesis works independently of playback.

## Audio playback

Piper synthesizes to a WAV file. We need to play that WAV file. Options:

1. **`sounddevice`** — Cross-platform, simple API, works well. Requires
   `portaudio` (bundled with the pip package on most platforms).
2. **`simpleaudio`** — Pure Python, no C dependencies, simpler API.
3. **`subprocess`** — Call a platform audio player (afplay on macOS,
   PowerShell `[Media.SoundPlayer]` on Windows). No extra dependencies
   but platform-specific and harder to control programmatically.

**Preferred: `sounddevice`** — cross-platform, programmatic control, can
detect when playback finishes (needed for queue semantics). Falls back to
subprocess platform player if `sounddevice` is not installed.

## Speech queue design

```
                         ┌──────────────┐
  enqueue("text") ──────►│  BoundedQueue │
                         │  (maxsize=2)  │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │ Worker Thread │
                         │  - dequeue   │
                         │  - adapt.speak│
                         │  - play audio │
                         └──────────────┘
```

- Queue maxsize = 2 (one waiting, one playing). If a third arrives, the
  waiting one is replaced (stale drop).
- Worker thread is a daemon so it doesn't block process exit.
- `flush()` joins the queue and waits for current playback to finish.
- `shutdown()` sets a stop flag, flushes, and joins the worker thread.

## Windows runtime constraints (from spec)

- Product CLIs must run from PowerShell/CMD.
- Use `subprocess` with argument arrays, NOT `shell=True`, for Piper calls.
- Use `pathlib.Path` for all file paths.
- Audio queue must not block the 50 Hz recorder loop.
- TTS must have a Windows-compatible backend.

## TTS configuration format

Extend `coach_config.toml`:

```toml
[llm]
provider = "ollama"
model = "glm-5.1:cloud"
api_key_env = "OLLAMA_API_KEY"
temperature = 0.3
max_tokens = 4096
base_url = "http://localhost:11434/v1"

[tts]
engine = "piper"                           # piper, pyttsx3, file
# piper_binary = "piper"                  # path to piper executable
# piper_model = "product/data/tts-voices/en_US-lessac-medium.onnx"
# output_file = "coach_output.wav"         # for file adapter
```

Environment variable overrides:
- `COACH_TTS_ENGINE` overrides `engine`
- `COACH_PIPER_BINARY` overrides `piper_binary`
- `COACH_PIPER_MODEL` overrides `piper_model`

## Testing

### Unit tests (no audio hardware needed)

1. **FileAdapter writes WAV** — synthesize with Piper to a file, verify file
   exists and has non-zero size. (Piper must be installed; skip if absent.)
2. **Pyttsx3Adapter instantiation** — verify import doesn't crash (skip on
   non-Windows or if pyttsx3 not installed).
3. **SpeechQueue enqueue/flush** — enqueue a text, flush, verify it was
   processed (using a mock adapter that records calls).
4. **SpeechQueue stale drop** — enqueue two texts, enqueue a third; verify
  the second was replaced by the third.
5. **SpeechQueue shutdown** — verify clean shutdown.
6. **Config loading with TTS section** — verify `[tts]` section loaded.
7. **Env var overrides for TTS config** — verify `COACH_TTS_ENGINE` etc.

### Integration tests (behind env var gate)

8. **End-to-end with Piper** — speak the default phrase, verify no errors.
   Requires Piper installed + a voice model. Manual smoke test.

### Manual smoke test (documented)

9. **PowerShell smoke** — documented command for Windows:
   ```powershell
   python -m lap_telemetry.coach.speak --text "Lost time in turn 3 exit"
   ```

## Acceptance criteria

- `TTSAdapter` abstract base class with `speak(text)` method.
- `PiperAdapter` calls Piper binary via subprocess, writes WAV, plays audio.
- `Pyttsx3Adapter` works as zero-install Windows fallback (skip if unavailable).
- `FileAdapter` writes audio to file without playback (for testing).
- `SpeechQueue` with non-blocking enqueue, worker thread, stale dropping, flush, shutdown.
- `speak` CLI works with `--text`.
- TTS configuration in `coach_config.toml` with env var overrides.
- Default phrase speaks successfully through Piper (manual smoke test).
- Unit tests pass (`bash scripts/test-summary.sh`).
- `npm run build` succeeds.
- `handoff.md` and `learnings.md` created.
- PowerShell smoke command documented.

## Non-goals

- Do not build the live telemetry pipeline (slice 5).
- Do not build LLM integration (done in slice 3).
- Do not build streaming/chunked audio (unnecessary for short utterances).
- Do not add volume or output device configuration (future work).
- Do not add voice selection beyond one default voice (future work).

## Definition of Done

- [ ] `tts_adapter.py` implemented with PiperAdapter, Pyttsx3Adapter, FileAdapter
- [ ] `speech_queue.py` implemented with enqueue, flush, shutdown, stale drop
- [ ] `speak` CLI entry point works
- [ ] TTS config added to `coach_config.toml`
- [ ] Unit tests pass
- [ ] Manual smoke test with Piper documented
- [ ] Full test suite passes
- [ ] Build succeeds
- [ ] `handoff.md` and `learnings.md` written