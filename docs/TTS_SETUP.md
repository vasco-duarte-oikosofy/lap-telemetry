# TTS Setup Guide

The race coach uses **Kokoro** as the primary TTS engine (natural
intonation). Piper is available as a secondary engine. Both run on
CPU alongside LMU without stealing GPU resources.

## Quick start

```bash
# 1. Install dependencies
pip3 install kokoro-onnx sounddevice

# 2. Download the Kokoro model and voices (~115 MB total)
mkdir -p product/data/tts-voices
curl -SL "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx" \
  -o product/data/tts-voices/kokoro-v1.0.int8.onnx
curl -SL "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" \
  -o product/data/tts-voices/kokoro-voices-v1.0.bin

# 3. Speak a coaching phrase
python3 -m lap_telemetry.coach.speak \
  --text "Box this lap, box this lap. Medium tyre."
```

If you hear a British male voice say the phrase, you're set up correctly.

## Engine comparison

| Engine | Natural? | Offline? | Latency (≤35 words) | Install size |
|--------|----------|----------|---------------------|-------------|
| **Kokoro** ⭐ | Good | ✅ Yes | ~100–300ms | ~115 MB |
| **Piper** | Flat, robotic | ✅ Yes | ~50–200ms | ~60 MB |
| **Edge TTS** | Good | ❌ Internet | ~200–500ms | None |
| **pyttsx3** | Very robotic | ✅ Yes | Instant | Small |

⭐ = recommended default

## Kokoro (primary engine)

### Why Kokoro?

Piper produces flat, monotone output with zero prosody — it sounds
robotic and lacks the assertive-yet-patient tone of an F1 race engineer.
Kokoro uses a StyleTTS2-derived architecture that models pitch, rhythm,
and emphasis, producing noticeably more natural speech.

### Install

```bash
pip3 install kokoro-onnx sounddevice
```

### Download model and voices

```bash
# From project root
mkdir -p product/data/tts-voices

# Kokoro int8 model (~88 MB)
curl -SL "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx" \
  -o product/data/tts-voices/kokoro-v1.0.int8.onnx

# Voice definitions (~27 MB)
curl -SL "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" \
  -o product/data/tts-voices/kokoro-voices-v1.0.bin
```

### Available voices

Male voices (recommended for race engineer persona):

| Voice | Description | Best for |
|-------|-------------|----------|
| `bm_daniel` ⭐ | British male | Calm, assertive race engineer |
| `bm_george` | British male | Slightly deeper |
| `bm_lewis` | British male | Softer |
| `am_adam` | American male | Clear midrange |
| `am_onyx` | American male | Deep, authoritative |

Female voices: `af_bella`, `af_nicole`, `af_nova`, `bf_emma`, `bf_lily`, and more.

Full list: see `k.get_voices()` after loading the model:
```python
from kokoro_onnx import Kokoro
k = Kokoro("product/data/tts-voices/kokoro-v1.0.int8.onnx",
           "product/data/tts-voices/kokoro-voices-v1.0.bin")
print(k.get_voices())
```

### Try different voices

```bash
# bm_daniel (default — British male)
python3 -m lap_telemetry.coach.speak \
  --text "Box this lap, box this lap. Medium tyre."

# am_onyx (American, deep)
python3 -m lap_telemetry.coach.speak \
  --text "Box this lap, box this lap. Medium tyre."

# Override via env var
COACH_KOKORO_VOICE=am_adam python3 -m lap_telemetry.coach.speak \
  --text "Box this lap, box this lap. Medium tyre."
```

### Voice quality note

The current default voice (`bm_daniel`) produces decent output but is
not fully natural. Sub-slice 04b.1 continues evaluation of engines
(ChatTTS, Qwen3-TTS, XTTS-v2) for more expressive intonation. The
adapter architecture makes it easy to swap engines without changing
the coach pipeline — just change `engine` and related config in
`coach_config.toml`.

## Piper (secondary engine — flat, robotic output)

Piper is a fast offline engine but produces monotone speech. It's kept
as a secondary option for environments where Kokoro can't be installed.

### Install

```bash
pip3 install piper-tts
```

### Download voice model

```bash
curl -SL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx" \
  -o product/data/tts-voices/en_US-lessac-medium.onnx

curl -SL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" \
  -o product/data/tts-voices/en_US-lessac-medium.onnx.json
```

### Use Piper

```bash
python3 -m lap_telemetry.coach.speak \
  --engine piper \
  --text "Lost time in turn 3 exit"
```

## Testing without speakers (CI)

Use the `file` adapter to skip audio playback entirely:

```bash
python3 -m lap_telemetry.coach.speak \
  --text "Test utterance" \
  --engine file \
  --output /tmp/test_output.wav

# Verify
cat /tmp/test_output.wav
```

## CLI reference

```bash
# Speak with default engine (kokoro, bm_daniel)
python3 -m lap_telemetry.coach.speak --text "Box this lap, box this lap."

# Choose engine
python3 -m lap_telemetry.coach.speak --engine kokoro --text "..."
python3 -m lap_telemetry.coach.speak --engine piper --text "..."
python3 -m lap_telemetry.coach.speak --engine file --text "..."

# Choose voice (kokoro only)
COACH_KOKORO_VOICE=bm_george python3 -m lap_telemetry.coach.speak --text "..."

# Adjust speed (kokoro only)
COACH_KOKORO_SPEED=0.95 python3 -m lap_telemetry.coach.speak --text "..."

# Synthesize to file without playing
python3 -m lap_telemetry.coach.speak --engine file --output /tmp/out.wav --text "..."

# Debug: show TTS engine info
python3 -m lap_telemetry.coach.speak --text "..." --debug
```

## Configuration

All TTS settings live in `coach_config.toml` under `[tts]`:

```toml
[tts]
engine = "kokoro"                   # kokoro | piper | pyttsx3 | file

# Kokoro settings
kokoro_model = "product/data/tts-voices/kokoro-v1.0.int8.onnx"
kokoro_voices = "product/data/tts-voices/kokoro-voices-v1.0.bin"
kokoro_voice = "bm_daniel"          # British male, race engineer feel
kokoro_speed = 1.05                 # slightly faster than default

# Piper settings (secondary engine)
# piper_binary = "python3 -m piper"
# piper_model = "product/data/tts-voices/en_US-lessac-medium.onnx"

# File adapter
# output_file = "coach_output.wav"
```

### Environment variable overrides

| Env var | Overrides |
|---------|-----------|
| `COACH_TTS_ENGINE` | `engine` |
| `COACH_KOKORO_MODEL` | `kokoro_model` |
| `COACH_KOKORO_VOICES` | `kokoro_voices` |
| `COACH_KOKORO_VOICE` | `kokoro_voice` |
| `COACH_KOKORO_SPEED` | `kokoro_speed` |
| `COACH_PIPER_BINARY` | `piper_binary` |
| `COACH_PIPER_MODEL` | `piper_model` |
| `COACH_TTS_OUTPUT_FILE` | `output_file` |

## Troubleshooting

### "Kokoro model not found"

Download the model files (see [Download model and voices](#download-model-and-voices)).
Verify they exist:

```bash
ls -lh product/data/tts-voices/kokoro-v1.0.int8.onnx    # ~88 MB
ls -lh product/data/tts-voices/kokoro-voices-v1.0.bin    # ~27 MB
```

### "kokoro-onnx is not installed"

```bash
pip3 install kokoro-onnx
```

### "sounddevice not available"

```bash
pip3 install sounddevice
```

KokoroAdapter falls back to platform audio players (`afplay` on macOS,
PowerShell `SoundPlayer` on Windows, `aplay` on Linux) if sounddevice
isn't installed.

### Wrong voice or speed

Check your config or override via env vars:

```bash
COACH_KOKORO_VOICE=bm_daniel COACH_KOKORO_SPEED=1.1 python3 -m lap_telemetry.coach.speak --text "test"
```