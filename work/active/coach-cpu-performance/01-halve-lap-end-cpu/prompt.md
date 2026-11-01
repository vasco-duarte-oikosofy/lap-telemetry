# Slice 01 — Halve lap-end coaching CPU work

**Status:** ✅ Complete in `4ffe4b7`. Both cold/warm CPU targets pass;
all facts/text and 12 real waveforms match exactly. Live race-FPS approval pending.

## Goal

Run this copy of the coach on real recorded lap data, establish a reproducible
baseline, then reduce local CPU work by at least 50% without changing facts,
utterance content, TTS voice/speed/quality or recording behavior.

## Execution

1. Register the feature suite with infrastructure guards and shared coach tests.
2. Run an original-code baseline: real lap comparison, deterministic utterance
   generation and real Kokoro synthesis. Use the same workload/dependencies for
   before/after. Record cold/warm CPU, child CPU, wall latency, peak and idle tail.
3. Profile the dominant cost. Write failing tests before production changes.
4. Implement only the smallest measured fix needed for <=50% CPU work. Preserve
   optional dependencies and all nonblocking/record-only behavior.
5. Verify facts/text/waveform parity, repeat the benchmark in fresh processes,
   report actual results and caveats. Do not infer simulator FPS from CPU data.
6. Feature tests, full --pw suite, build, handoff/learnings and commits on main.
7. Mark complete with implementation hash. Only then create planning prompts for
   further measured opportunities toward 10%; do not implement another slice.

## Non-goals

No track/reference/model edits, coaching semantic changes, cloud-provider changes,
new TTS engine, recorder rewrite, or unmeasured blanket optimizations. No claim
of fixing in-game FPS until the user tests it live.
