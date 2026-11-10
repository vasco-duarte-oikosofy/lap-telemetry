# Bug 34 — Recordings contain duplicated rows with a stalled clock

## Symptom

Three committed laps contain more rows than their recording clock can account
for, and the surplus rows carry a **frozen** `session_time_s` / `lap_time_s`
while `lap_distance_m` keeps advancing. The delta-t trace then collapses over
that stretch and corner facts become nonsense.

Worst case, Paul Ricard 3A / DKR, session
`session_20260524T141613Z_paul-ricard---3a_lmu.parquet`, segment 2 (lap 2):

| quantity | value |
|---|---|
| authoritative duration | 79.882 s (a normal flying lap) |
| rows in segment | 6 235 |
| `session_time_s` span | 80.0 s |
| rows per (second × 50 Hz) | **1.56×** |
| longest run of identical `lap_time_s` | 2 244 samples, starting at 79.882 s |
| distance during that freeze | 3 510 m → 3 753 m with no clock advance |
| reported corner fact | **Pont minimum speed: −3.499 s (a "gain")** on a lap that is +2.716 s |

Across the 315 eligible laps in `dev/sessions`, rows/(span × rate) is
1.000 ± 0.002 for 312 laps. The three outliers:

| rows/(span×rate) | session | segment |
|---|---|---|
| 1.559 | `20260524T141613Z_paul-ricard---3a` | 2 |
| 1.383 | `20260510T093245Z_circuit-de-barcelona` | 0 |
| 1.139 | `20260510T131245Z_circuit-de-barcelona` | 0 |

## Root cause

Unknown at the recorder level. Either the writer appends frames faster than the
nominal rate for a stretch, or the shared memory stops advancing while the poll
loop keeps writing rows (a pause or finish state). The tell is that the extra
rows are *stalled*: clock frozen, distance still moving.

Adjacent to bug 30 (abandoned final lap with a frozen game clock) but different:
here the lap is complete and has a valid duration, so every duration-based guard
passes.

## Impact

Any consumer that resamples by distance sees zero elapsed time across the frozen
stretch. Over a 243 m window that is a phantom multi-second swing, and it lands
in whatever corner owns that distance — here the last corner. It corrupts
`minimum_speed` / `exit` losses and every spread derived from them.

## Current mitigation (analysis side, `session-debrief` slice 03)

`session_laps.classify_laps` rejects a lap whose `frames/(span × rate)` is
outside 1.00 ± 0.10 as `short`, with a reason, and the inventory's invariant
audit justifies the gate. That removes exactly the three laps above and nothing
else. It protects the debrief and any future consumer of the inventory; it does
**not** fix the recording.

## Proper fix (not yet done)

Find where `SessionWriter` can append a frame whose `session_time_s` did not
advance while distance did, and either skip the frame or split the segment. Add
a recorder-side warning when a shard's rows/span drifts beyond 2%.

## Status

🐛 Open. Mitigated on the analysis side in `session-debrief` slice 03. Needs a
recorder investigation and a live repro.
