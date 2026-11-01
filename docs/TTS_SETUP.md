# TTS Setup Guide

The race coach uses **Kokoro** as the primary TTS engine (natural
intonation). It runs on CPU alongside LMU without stealing GPU resources.
Kokoro uses one inference thread by default, sequential execution, and no idle
worker spinning to avoid occupying the simulator's cores.

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

## Kokoro

### Why Kokoro?

Kokoro uses a StyleTTS2-derived architecture that models pitch, rhythm,
and emphasis, producing natural-sounding speech — dramatically better
than flat monotone engines.

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
engine = "kokoro"                   # kokoro | pyttsx3 | file

# Kokoro settings
kokoro_model = "product/data/tts-voices/kokoro-v1.0.int8.onnx"
kokoro_voices = "product/data/tts-voices/kokoro-voices-v1.0.bin"
kokoro_voice = "bm_daniel"          # British male, race engineer feel
kokoro_speed = 1.05                 # slightly faster than default
kokoro_cpu_threads = 1              # positive integer; 0/auto is rejected

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
| `COACH_KOKORO_CPU_THREADS` | `kokoro_cpu_threads` |
| `COACH_TTS_OUTPUT_FILE` | `output_file` |

### CPU budget while racing

Restart the coach to pick up the default one-thread CPU session. No new launch
flag is required and the cloud/local/template utterance selection is unchanged.
The model, voice and speaking speed are unchanged; every utterance is still
synthesized. No process-global OMP/BLAS variables or recorder priorities change.

An explicit `COACH_KOKORO_CPU_THREADS=2` (or TOML value 2) can trade additional
CPU for latency on other hardware. Zero, negative and noninteger values are
rejected rather than silently restoring ORT's all-core pool. Spinning remains
disabled at every budget. This adapter deliberately uses CPUExecutionProvider;
GPU/offload needs separate measurement alongside the simulator.

Kokoro must support `Kokoro.from_session` so the bounded session can be supplied.
If the coach reports an old API, run `pip install --upgrade kokoro-onnx`. It
never silently falls back to the unbounded constructor.

For reproducible before/after measurements, see
[coach CPU performance](specs/coach-cpu-performance.md) and
`dev/scripts/benchmark_coach_cpu.py --help`. Timing benchmarks run serially,
outside the parallel test suite. Simulator FPS still requires live validation.

### Live CPU-seconds after every utterance

After restarting the live coach, each completed speech attempt prints a line
on stderr, even without `--debug`:

```text
lap-telemetry: [coach] speech-cpu utterance=1 status=ok cpu_s=14.200 wall_s=23.100 synthesis_cpu_s=14.000 synthesis_wall_s=14.050 scope=process text="..."
```

Numbers above illustrate the format, not a race measurement:

- `cpu_s`: process CPU-seconds during the whole speech attempt, including playback.
- `wall_s`: elapsed seconds for that attempt, including waiting for audible audio.
- `synthesis_cpu_s` / `synthesis_wall_s`: Kokoro loading + synthesis only, before
  playback. First use includes lazy model load. Other engines report `na`.
- `utterance`: sequential ID per queue/run; `text`: actual delivered text, escaped
  onto one line. Dropped pending utterances do not generate fake CPU records.
- `status=error`: a failed attempt, not successful speech; subsequent speech can
  continue. Failed synthesis reports its fresh partial timing when available.

**Scope matters:** CPU counters include ALL threads in the coach process (native
ONNX workers AND concurrent recorder/analysis activity), not just the speech
thread. They exclude the simulator, child processes/external LLM servers and
analysis before speech starts. They are not precisely attributed whole-lap CPU
costs, and do not replace the controlled benchmark's child-inclusive accounting.
CPU-seconds are work, not CPU percentage; playback waiting mainly adds wall time.

To save real-race evidence, append this to your usual PowerShell coach command:

```powershell
2>&1 | Tee-Object -FilePath coach-race.log
```

Keep the full log (lap/analysis timing plus these records). To extract just these
lines: `Select-String -Path coach-race.log -Pattern '\[coach\] speech-cpu'`.
In Bash, append `2>&1 | tee coach-race.log` instead. No new launch flag is needed.

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