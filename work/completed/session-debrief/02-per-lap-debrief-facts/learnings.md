# Learnings — Slice 02: per-lap debrief facts

- **An extracted reference lap cannot re-derive its own duration, and the error
  is large.** `authoritative_duration` prefers the difference between
  consecutive telemetry lap-start ETs, but an extracted reference is a single
  segment, so there is no next ET and it falls back to the scorer's
  `mLastLapTime` — which lags a lap and reads high. Across the 35 committed
  references, 23 have no `authoritative_lap_time_s` stamp, and the re-derived
  duration disagrees with the filename by up to **0.97 s** (Lusail
  111.975 → 112.948, Laguna Seca 81.495 → 82.298). The filename is the value the
  export certified and `validate_reference_laps.py` checks, so the debrief uses
  it. Paul Ricard: 1:17.166 certified vs 1:17.626 re-derived.
- **The live coach still re-derives.** `compare_laps` calls
  `segment_duration(..., allow_same_segment_scoring=True)`, so on the same combo
  its `lap_time_delta_s` is 0.46 s larger than the debrief's. Per-corner losses
  are unaffected (they come from the delta-t trace), but the spoken lap summary
  is not. Sharing `session_inputs.reference_lap_time_s` with the live coach
  would change spoken numbers, so it is deferred — see the handoff TODO.
- **The live slow-lap guard is wrong for a debrief.** `is_implausibly_slow_lap`
  rejects anything past 1.15× the reference. Paul Ricard segment 13 (1:30.693
  vs a 1:17.166 reference = 1.17×) is a traffic/mistake lap, not a pit stop: the
  inventory already proved it never stopped and is under 1.20×. Losing it would
  hide exactly the lap the coach should talk about. `compare_lap_tables` gained
  `reject_implausibly_slow`, defaulting to true for the live coach.
- **Do not widen the inventory's status vocabulary from the analysis layer.** The
  first version set `record.status = "unanalysable"` when the comparator rejected
  a lap; that silently breaks the invariant audit (which validates statuses) and
  mutates a record another layer owns. The analysis now keeps its own
  `ExcludedLap` with that status instead.
- **Uncapped phases are a lot of phases: 23 for one lap, 151 KB of JSON for 19
  laps.** That confirms the spec's decision that the model gets a compact report
  and on-demand drill-downs, never this payload.
- **Cost is post-session only.** 19 laps ≈ 4.5 s, almost all of it the Node
  delta-t pipeline spawning once per lap. Acceptable after a stint, hopeless for
  the live loop, which is why the live coach keeps its own incremental path.
- **`lap_number` really is not a lap identity.** Segments 1 and 4 of the Paul
  Ricard fixture are both lap 1, at 1:24.804 and 1:22.491. Any implementation
  keyed on lap number would have reported one of them twice.
