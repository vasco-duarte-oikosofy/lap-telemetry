# Installing TTS Engines

The coach uses Kokoro as the primary TTS engine (natural intonation).
Piper is available as a secondary engine. Both run entirely on CPU.

## Primary: Kokoro (recommended)

Kokoro produces natural-sounding speech with proper intonation —
dramatically better than Piper's flat output. Default voice is
`bm_daniel` (British male, race engineer feel).

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

American male: `am_adam`, `am_echo`, `am_eric`, `am_fenrir`, `am_liam`,
`am_michael`, `am_onyx`, `am_puck`

British male: `bm_daniel`, `bm_george`, `bm_fable`, `bm_lewis`

American female: `af_alloy`, `af_bella`, `af_nicole`, `af_nova`, `af_river`, `af_sarah`, `af_sky`

British female: `bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`

### Configuration

```toml
[tts]
engine = "kokoro"
kokoro_model = "product/data/tts-voices/kokoro-v1.0.int8.onnx"
kokoro_voices = "product/data/tts-voices/kokoro-voices-v1.0.bin"
kokoro_voice = "bm_daniel"        # British male, race engineer feel
kokoro_speed = 1.05               # slightly faster than default
```

### Smoke test

```bash
python3 -m lap_telemetry.coach.speak \
  --text "Box this lap, box this lap. Medium tyre."
```

## Secondary: Piper (flat, robotic output)

Piper is available as a fallback engine. Its output lacks natural
intonation but is very fast and fully offline.

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

Use the `file` adapter to skip audio playback:

```bash
python3 -m lap_telemetry.coach.speak \
  --text "Test utterance" \
  --engine file \
  --output /tmp/test_output.wav
```

## All configuration options

```toml
[tts]
engine = "kokoro"                   # kokoro | piper | pyttsx3 | file

# Kokoro settings
kokoro_model = "product/data/tts-voices/kokoro-v1.0.int8.onnx"
kokoro_voices = "product/data/tts-voices/kokoro-voices-v1.0.bin"
kokoro_voice = "bm_daniel"
kokoro_speed = 1.05

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
| `COACH_PIPER_BINARY` | `piper_binary` |
| `COACH_PIPER_MODEL` | `piper_model` |
| `COACH_TTS_OUTPUT_FILE` | `output_file` |