# Coach CPU performance

## Goal

Reduce race-coach CPU interference at lap boundaries while retaining facts,
utterance content, voice, speed and audio quality. First delivery must measure
at least 50% lower local CPU seconds for the same replay workload; investigate
further slices toward at most 10% of the original cost. Do not claim simulator
FPS gains without a live simulator measurement.

## Measurement contract

- Run the original and changed coaching code on the same machine, dependency
  versions, real completed lap and utterance; retain raw samples and provenance.
- Include real comparison, text generation and real Kokoro ONNX synthesis.
  For reproducibility, use deterministic text generation instead of a billed,
  nondeterministic cloud call. Do not change the user's cloud-LLM selection.
- Suppress audible playback only. Validate generated waveform, duration and
  sample rate. Record first-use/cold and subsequent/warm events separately.
- Primary work metric: local CPU seconds, including native inference threads;
  measure Node child CPU separately, not just Python wall time. Also report
  wall latency, sampled peak CPU and idle tail after synthesis.
- Repeat fresh-process runs; do not compare an old cold run to a new warm run.
  Keep benchmarks outside parallel CI to avoid noisy timing assertions.
- A sleeping/delayed or disabled coach does not satisfy the CPU-work target.
  Results must be output-equivalent and latency must remain practical.

## First slice

Profile lap-end comparison/text/synthesis, identify the dominant local cost and
make the smallest evidence-backed change reaching the 50% target. Any controls
must have safe defaults and tests; never mutate process-global thread settings
that could harm the recorder or unrelated libraries. Preserve record-only mode,
nonblocking queue behavior and optional dependency handling.

The measured first-slice change is a session-local CPUExecutionProvider session:
`kokoro_cpu_threads=1` by default, sequential inter-op execution, and both ORT
spinning flags disabled. A positive integer thread budget may be configured in
`[tts]` or `COACH_KOKORO_CPU_THREADS`; zero/auto and invalid values are rejected.
Reuse the lazily loaded session. Require Kokoro.from_session rather than falling
back silently to its unrestricted constructor. Do not alter OMP/BLAS variables,
recorder priority, cloud provider, model weights or speech content.

## Live race telemetry

Every live SpeechQueue attempt prints one flushed stderr speech-cpu record after
speech/playback returns (including failures), independently of debug log level.
Report sequential utterance identity, escaped actual text, status, whole-attempt
process CPU/wall seconds, and optional pre-playback Kokoro synthesis CPU/wall.
Do not count stale pending drops as spoken work. Record cold load and failed
partial synthesis afresh; never reuse timing from a previous utterance.

Use process_time so native ONNX threads count. Label scope=process: concurrent
recorder/analysis threads are included, while child processes, simulator/external
LLM work and analysis before speech starts are excluded. This cheap live signal
is not precise per-job attribution or the offline child-inclusive total. Closed
log pipes must not kill speech delivery. No polling/profiler dependency is needed.

## Further work

Plan follow-ups only after the first slice's measurements identify the remaining
costs. Candidate areas: reference/resampling reuse, session-column projection,
first-use preparation, subprocess reuse and isolated low-priority workers.
Each needs its own output-parity tests and a comparison to the original baseline.
CPU-work reduction and reduced scheduling interference are different claims.
