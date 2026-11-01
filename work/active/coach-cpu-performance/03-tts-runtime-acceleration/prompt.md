# Slice 03 — Reduce real synthesis-miss CPU cost

**Status:** 📋 Planned, NOT started. Requires explicit selection before work.
Can be selected before slice 02 if real utterance repetition is low.

## Goal

Reduce the remaining ~13.89 CPU-s per synthesis miss, not merely amortize repeat
phrases. Target <=5.69 synthesis CPU-s plus ~0.33 comparison CPU-s, approaching
<=6.01 total CPU-s/event (10% of the ORIGINAL warm baseline). No guarantee is
made before profiling and hardware capability checks.

## Execution

1. Read slice 01 artifacts/spec, reproduce the no-spin one-thread baseline on
   the target machine and identify available CPU/GPU/NPU execution providers.
2. Spike ONNX operator profiling separately from unbiased timing runs. Identify
   dominant kernels, unsupported-provider fallbacks and memory cost. Do not
   equate summed parallel operator wall times with CPU-seconds.
3. Compare evidence-backed CPU-runtime/graph options first. If needed, evaluate
   an explicitly opt-in accelerated provider with the SAME Kokoro model/voice.
   Isolate dependency experiments; do not overwrite the working CPU environment.
4. Select ONE proven route. Write failing parity/config/fallback tests before
   production code. Preserve the current bounded CPU default and lazy reuse.
   Record any deliberate runtime/provider version changes explicitly in the
   benchmark contract; never silently pretend the environments are identical.
5. Measure unique utterances of several lengths, fresh loads and steady-state
   misses. Include child/native CPU, memory, wall latency and accelerator use.
   Validate facts/text/rate/duration and audio parity; any numerical tolerance
   needs explicit justification and listening review, not a silent quality cut.
6. For GPU/NPU offload, test alongside the simulator: CPU savings that worsen
   race frame times are not success. Measure p95/p99 frame times and contention.
7. Retain only a measured winner (or document a negative capability result),
   run feature/full --pw tests and build, commit/handoff/update plan, then stop.

## Acceptance and boundaries

A measured synthesis-miss improvement with unchanged spoken content/voice and
no game-frame-time regression. State honestly whether 10% total CPU is reached,
and report both cold and warm results. GPU work is not free just because it
is no longer CPU work. If unavailable or harmful, preserve the current CPU path.

No new TTS engine, lower-quality model, provider switch for the coaching LLM,
shorter utterances, disabled coaching or benchmark-only sleep/rate-limit tricks.
Moving cold work to startup smooths a spike but is not a CPU-work reduction.
