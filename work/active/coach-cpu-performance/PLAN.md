# Coach CPU performance

Spec: [coach-cpu-performance](../../../docs/specs/coach-cpu-performance.md).

Goal: halve measured lap-end local CPU work first; then plan the path toward 10%.
Feature tests: `bash scripts/test-summary.sh --feature coach-cpu-performance`.

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-halve-lap-end-cpu` | ✅ `4ffe4b7` | Warm CPU 60.14 → 14.20 s (76.38% less), cold 75.88% less, sampled TTS peak 87.70% lower; facts/text/all 12 waveforms identical |
| `02-bounded-speech-cache` | 📋 Planned, not started | Measure real repeat rate, then bounded exact-waveform reuse if justified; ~59% synthesis-work avoidance would reach the 10% total budget |
| `03-tts-runtime-acceleration` | 📋 Planned, not started | Profile and reduce unique-utterance synthesis misses toward <=5.69 CPU-s; CPU runtime first, optional hardware offload only with frame-time/quality proof |
| `04-reuse-comparison-work` | 📋 Planned, lower priority | Profile actual live shards, then safely reuse invariant reference/preparation work; only ~2.3% of current remaining CPU on this workload |
| `05-isolated-speech-worker` | 📋 Planned, conditional | If live race stalls persist, isolate speech at lower worker-only priority; prove scheduling/FPS gains separately from CPU-work savings |
| `06-live-utterance-cpu-report` | ✅ `72e8f41` | Always-visible process CPU-s after each speech attempt, separate Kokoro synthesis timing, real cold/warm waveform parity and race-log collection instructions |

Slices 01 and 06 are complete. Slices 02–05 remain **planning only**, with no
implementation started. User selection is required before any of those options
proceeds; live race data from the new CPU reports is pending.

[Measured evidence](01-halve-lap-end-cpu/artifacts/benchmark.md): warm cost is now
23.62% of original, not yet 10%. The next total budget is ~6.01 CPU-s/event;
~97.7% of remaining work is synthesis. Cache effectiveness and hardware offload
are hypotheses, not guaranteed savings. Prefer 03 over 02 for mostly unique
cloud wording; move 05 forward if live frame stalls remain. Slice 04 alone
cannot bridge the measured gap. Live race-FPS approval remains pending.
