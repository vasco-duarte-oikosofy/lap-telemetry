# Slice 02 — Bounded exact-utterance audio reuse

**Status:** 📋 Planned, NOT started. Requires explicit selection before work.

## Goal and hypothesis

Avoid redundant synthesis without changing a single utterance or waveform.
Slice 01 uses 14.20 CPU-s/event (23.62% of original). Its remaining synthesis
cost is ~13.89 CPU-s. Reaching the original 10% budget (~6.01 CPU-s/event) by
caching alone needs about **59% real synthesis-work avoidance**. That hit rate
is unproven, especially with nondeterministic cloud-generated wording.

## Execution

1. Read slice 01's benchmark, spec and handoff. Register this slice's tests in
   the existing coach-cpu-performance feature suite before implementation.
2. Capture/replay a representative multi-lap utterance trace with the user's
   actual cloud/template mode, including a held-out session and novel phrases.
   Determine exact-repeat rate first. Do not call the cloud repeatedly just
   to manufacture a benchmark; use captured text with source/provenance.
3. Spike a byte-bounded exact-audio cache. If the trace shows no material gain,
   retire the hypothesis with evidence rather than shipping speculative caching.
4. If justified, write failing tests then add only exact full-utterance reuse.
   Keys must include text, model identity, voice, speed and all synthesis options.
   Bound memory by bytes, define eviction, never mutate stored waveforms, and
   never omit playback when synthesis is reused. Failed synthesis is not cached.
5. Benchmark hits AND misses on the held-out trace; report memory, cold cost,
   miss cost, cache lookup CPU and weighted total CPU versus the ORIGINAL and
   slice-01 baselines. Preserve current one-thread/no-spin miss behavior.
6. Verify every output against uncached synthesis and existing queue semantics.
   Run feature/full --pw tests and build. Commit, update plan, handoff and stop.

## Acceptance

A measured reduction on representative varied utterances, bounded memory and
sample-identical audio/text. Report actual distance from the <=6.01 CPU-s/event
budget. No promised 10% result unless the held-out workload actually passes it.
A documented negative result/retirement is valid if hit rate vetoes the feature.

## Non-goals

No fuzzy matching, rephrasing, fragment stitching, dropped utterances, global
unbounded memoization, new model/provider, or queue/process rewrite. Replaying
one identical phrase four times and claiming real-world 90% savings is invalid.
