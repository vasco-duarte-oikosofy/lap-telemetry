# Handoff — Slice 01: halve lap-end coaching CPU

## Delivered

The default Kokoro session now uses **one CPU inference thread**, sequential
inter-op execution and disabled intra/inter-op spinning. It is still lazy-loaded
once and reused. The exact same model, voice, speed and text are synthesized.
No process-wide OMP/BLAS settings, scheduling priorities, recorder behavior,
coaching facts, cloud-provider selection or speech-queue semantics were changed.

- `product/python/lap_telemetry/coach/tts_adapter.py`: explicit CPUExecutionProvider
  InferenceSession, supplied through Kokoro.from_session. No unrestricted fallback.
- `product/python/lap_telemetry/coach/coach_config.py`: positive integer
  kokoro_cpu_threads, default 1; TOML/environment parsing and validation.
- `coach_config.toml`: explicit value 1. Restart the coach to apply it.
- `COACH_KOKORO_CPU_THREADS` overrides TOML. Values 0/auto, negative, boolean or
  noninteger budgets are rejected. An explicit larger budget trades CPU for
  possible latency improvements on different hardware; spinning stays off.
- Missing optional packages still fail only when Kokoro is used. An old Kokoro
  API gives a clear upgrade error instead of silently reverting to all-core use.
- Setup/CPU-budget documentation: `docs/TTS_SETUP.md`.

## Measured acceptance (not a simulator-FPS claim)

Original: `1bd0890`, before production edits. Real Long Beach practice lap 11,
full session Parquet -> LiveFactGenerator -> deterministic TemplateAdapter ->
real Kokoro synthesis. Cloud calls and audible playback excluded, live cloud
configuration untouched. Three fresh processes per campaign, each one cold and
three warm events. Exact native/Python CPU plus completed-child CPU included.

| Event metric | Original | New | Reduction |
|---|---:|---:|---:|
| Median cold CPU | 63.546875 s | 15.328125 s | 75.88% |
| Median warm CPU | 60.140625 s | 14.203125 s | 76.38% |
| Worst sampled TTS CPU peak (100%=one core) | 848.08% | 104.28% | 87.70% |
| Median warm wall time, including 1 s idle observation | 15.237 s | 15.202 s | Essentially unchanged |

All facts/text and all **12 real waveforms are sample-identical**, including
sample rate/duration. Cold and warm <=50% gates both pass. No work is skipped.
New warm CPU is 23.62% of baseline: meaningful progress, but **not yet 10%**.
Around 97.7% of remaining CPU is synthesis; comparison-only changes cannot
bridge that gap on this workload. See `artifacts/benchmark.md` for details.

## Benchmark tooling and evidence

- `dev/scripts/benchmark_coach_cpu.py`: serial fresh-process campaigns, sampled
  tree CPU peaks, exact stage/event summaries; refuses nonempty output dirs.
- `dev/scripts/coach_cpu_replay.py`: real lap-to-audio workload, output capture.
- `dev/scripts/coach_cpu_metrics.py`: exact completed-child CPU accounting
  (Windows GetProcessTimes / Unix getrusage), including Node work.
- `dev/scripts/compare_coach_cpu.py`: <=50% CPU, latency and exact output gates.
  Resolves the supplied campaign directories so archived evidence can relocate.
- Raw successful campaigns/arrays: ignored `var/tmp/coach-cpu/before/` and
  `var/tmp/coach-cpu/after-verified/`. Reports retain original output path strings;
  metadata need not be rewritten after relocation.
- Committed `artifacts/`: full compact reports, all six trial records, comparison
  gates, waveform hashes and benchmark explanation. Raw audio arrays stay local.
- Dependencies installed in the venv before baseline: Kokoro 0.6.1, ORT 1.23.2,
  psutil 7.2.2. Same dependency versions in both campaigns. Existing model/voices
  were already present. No new base/mandatory recorder dependency was added.

```bash
export PATH="$PWD/.venv/Scripts:$PATH" PYTHONUTF8=1
bash scripts/test-summary.sh --feature coach-cpu-performance
python dev/scripts/benchmark_coach_cpu.py --out var/tmp/coach-cpu/new-run
python dev/scripts/compare_coach_cpu.py \
  var/tmp/coach-cpu/before var/tmp/coach-cpu/new-run \
  --out var/tmp/coach-cpu/new-comparison.json
```

Do not put heavy real-inference timing runs in the parallel CI suite. Unit tests
mock the optional engine to assert session policy, reuse, retry, dependency errors,
config validation and unchanged voice/text/playback. Tiny deterministic benchmark
fixtures test child-CPU accounting math and rejection of bad output/CPU results.

## Verification

- Red-before-code evidence: `artifacts/test-first-red.txt`.
- Feature suite: **373 assertions / 11 scripts pass**.
- Full --pw suite: **1772 assertions / 73 scripts pass**, with the same temporary
  Windows ESM-path adapter used by previous slices (stock bug 20 remains).
- npm run build passes; product/dist/compare.html is current and byte-unchanged
  because this slice changes Python, not the web bundle.
- git diff --check clean. No data/model/reference assets changed.

## Caveats and next work

Live race FPS, recorder flush CPU and external LLM-server CPU were not measured.
The benchmark reproduces the coach's after-lap local workload, not the simulator.
Ask the user to restart the coach and test an actual race line crossing. Do not
present measured CPU savings as guaranteed FPS improvement on other hardware.

Two incomplete measurement attempts are excluded wholesale, not cherry-picked:
one outer tool timeout and one Windows sampler marker sharing violation. The
marker instrumentation was fixed; the complete after-verified campaign passed.

A pre-existing, unregistered test_nonblocking_coach_pipeline.py fixture fails on
original code: it supplies only 1900 m for a 5000 m track, correctly tripping the
80% partial-lap guard. It was discovered while assembling the feature suite,
not caused by this change. It was not retained in this TTS-only suite or modified.
Existing live-after-lap/queue tests pass. Revisit that invalid fixture if a later
slice changes worker orchestration; do not weaken partial-lap rejection.

Main already had 11 unrelated local commits ahead of origin at slice start.
Do not publish those implicitly as part of this performance-only delivery.
Follow-up prompts are planning only; no second implementation slice is started.
