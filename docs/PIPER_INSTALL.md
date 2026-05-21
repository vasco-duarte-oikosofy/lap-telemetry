# Installing Piper TTS

This project uses [Piper](https://github.com/rhasspy/piper) for local,
offline text-to-speech. Piper runs entirely on CPU alongside LMU without
stealing GPU resources, and produces identical audio on macOS and Windows.

## Quick install (macOS / Linux)

### Option A: Python package (recommended)

```bash
pip3 install piper-tts
```

This installs Piper as a Python module, invoked via `python3 -m piper`.
No standalone binary needed. This is the default `piper_binary` in
`coach_config.toml`.

### Option B: Standalone binary

Download from [Piper releases](https://github.com/rhasspy/piper/releases):

```bash
# macOS (Apple Silicon)
curl -SL https://github.com/rhasspy/piper/releases/latest/download/piper_macos_aarch64.tar.gz | tar xz -C /usr/local/bin/

# macOS (Intel)
curl -SL https://github.com/rhasspy/piper/releases/latest/download/piper_macos_x64.tar.gz | tar xz -C /usr/local/bin/

# Linux (x86_64)
curl -SL https://github.com/rhasspy/piper/releases/latest/download/piper_linux_x86_64.tar.gz | tar xz
sudo mv piper/piper /usr/local/bin/
```

If using the standalone binary, set `piper_binary = "piper"` in
`coach_config.toml` (or the `COACH_PIPER_BINARY` env var).

## Windows

```powershell
pip install piper-tts
```

Or download `piper_windows_amd64.zip` from the releases page and add to
PATH.

## Voice model

Download the English (US) Lessac medium model — good quality, ~60 MB:

```bash
# From project root
mkdir -p product/data/tts-voices

curl -SL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx" \
  -o product/data/tts-voices/en_US-lessac-medium.onnx

curl -SL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" \
  -o product/data/tts-voices/en_US-lessac-medium.onnx.json
```

The model path is already configured in `coach_config.toml`:

```toml
[ tts]
piper_model = "product/data/tts-voices/en_US-lessac-medium.onnx"
```

Other voices are available at
<https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0>.

## Audio playback dependencies

Piper synthesizes to a WAV file; playback requires one of:

| Package | Install | Notes |
|---------|---------|-------|
| `sounddevice` | `pip install sounddevice` | Preferred — cross-platform, programmatic |
| Platform player | Built-in | `afplay` (macOS), `PowerShell SoundPlayer` (Windows), `aplay` (Linux) |

```bash
pip install sounddevice   # recommended playback library
```

## Smoke test

After installing Piper + voice model:

```bash
# From project root
echo "Hello world" | python3 -m piper \
  --model product/data/tts-voices/en_US-lessac-medium.onnx \
  --output_file /tmp/test.wav

# Or use the coach speak CLI:
python3 -m lap_telemetry.coach.speak \
  --text "Lost time in turn 3 exit — minimum speed 10 km/h lower"
```

## Testing without speakers (CI)

Use the `file` adapter to skip audio playback:

```bash
python3 -m lap_telemetry.coach.speak \
  --text "Test utterance" \
  --engine file \
  --output /tmp/test_output.wav
```

## Configuration

All TTS settings live in `coach_config.toml` under `[tts]`:

```toml
[tts]
engine = "piper"                                                # piper | pyttsx3 | file
piper_binary = "python3 -m piper"                              # or path to standalone binary
piper_model = "product/data/tts-voices/en_US-lessac-medium.onnx"
# output_file = "coach_output.wav"                              # for file adapter
```

### Environment variable overrides

| Env var | Overrides |
|---------|-----------|
| `COACH_TTS_ENGINE` | `engine` |
| `COACH_PIPER_BINARY` | `piper_binary` |
| `COACH_PIPER_MODEL` | `piper_model` |
| `COACH_TTS_OUTPUT_FILE` | `output_file` |