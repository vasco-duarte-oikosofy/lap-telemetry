# Slice 06 — Print CPU-seconds after each live utterance

**Status:** In progress. User explicitly requested this addition; slices 02–05
remain planning only and are not selected for implementation.

## Goal

Always print a low-overhead CPU-s report after each live-coach speech attempt,
so the user can collect real race data without enabling debug logging. Include
elapsed wall time, status, utterance identity/text and separate Kokoro synthesis
CPU/wall time so audible playback does not obscure the expensive phase.

## Metric contract

Use process_time, not thread_time: native ONNX inference threads must count.
Label scope=process: concurrent recorder/analysis threads are included; simulator,
external child processes/LLM servers and work before speech starts are excluded.
This is not a precisely attributed whole-lap coaching CPU total. Include first
model load in cold synthesis. Never mistake playback waiting for CPU work.

## Execution

1. Re-evaluate the existing coach-cpu-performance suite; add failing deterministic
   tests for reporting after initial and chained pending speech, failures/retry,
   stale drops, default visibility, exact clock math and Kokoro stage boundaries.
2. Add lightweight stage snapshots in Kokoro and one always-visible report per
   actual speech attempt in SpeechQueue. Do not change public speak() returns,
   queue behavior, thread policy, voice, text or playback. No polling/psutil needed.
3. Run the real local Kokoro model through the queue without audible playback to
   verify the emitted line on real synthesis. Save concise evidence.
4. Document fields/scope and how to capture logs from the usual race command.
5. Feature tests, full --pw suite, build, handoff/learnings, commit on main and
   mark this slice complete with its implementation hash. Stop.

## Non-goals

No other performance slice, new cache/provider/process, precise per-job CPU
attribution across concurrent threads, simulator profiling or session-data edits.
