# Slice 05 — Isolate remaining speech interference from the recorder/game

**Status:** 📋 Planned, NOT started. Requires explicit selection before work.
Conditional priority: select earlier if live race stalls remain after slice 01.

## Goal

Prevent remaining synthesis from disrupting race/recorder scheduling. This is
an interference/FPS objective, NOT automatically another reduction in total CPU
work. Keep CPU-seconds and frame-time claims separate. A lower-priority worker
that merely runs longer does not satisfy the 10%-of-original work target.

## Execution

1. Collect actual race line-crossing evidence after restarting the slice-01 coach:
   frame-time trace, coach stage timing, recorder flush cost and CPU per process.
   Where no simulator is available, use a clearly labelled scheduling/recorder
   heartbeat harness and do not claim a measured game-FPS improvement.
2. Spike a long-lived isolated TTS worker with session-local one-thread/no-spin
   inference and lower OS priority. Never lower the recorder/parent process
   priority or hard-code arbitrary core affinity. Verify whether isolation helps
   before adding permanent orchestration.
3. Write failing tests for nonblocking delivery, bounded pending work, stale-drop
   policy, worker failure/restart and shutdown. The old unregistered nonblocking
   fixture ends at 1900 m for a 5000 m track: repair that fixture if needed for
   this orchestration coverage; do not weaken the production partial-lap guard.
4. If justified, implement only speech-worker isolation. Keep the engine loaded,
   avoid per-utterance process spawning, preserve voice/audio and active-playback
   behavior, and ensure IPC cannot block the recorder or grow without bound.
   OS-priority failure must be logged and safely fall back, not break recording.
5. Measure p95/p99 frame/heartbeat times, dropped telemetry, CPU-seconds, memory,
   startup/utterance latency and shutdown reliability under synthesis load.
   Report costs of the additional process and any priority-induced latency.
6. Confirm no record-only workers, zombies, hung shutdown or reordered/skipped
   delivered speech. Run feature/full --pw tests/build, commit and update all
   handoff/plan artifacts. Stop; do not combine another optimization slice.

## Acceptance

A demonstrated reduction in scheduling interference without recording/data loss,
output/queue regressions or unbounded resource growth. Real FPS claims require
real simulator evidence. Whole CPU work must not be relabelled as 90% lower
simply because it moved to a different PID or ran at lower priority.

## Non-goals

No recorder rewrite, inference/model/provider changes, global process-priority
changes, busy-wait rate limiting or silently suppressing coaching to hide stalls.
