# Bug 19 — Session restart causes duplicate lap-number rows in snapshot → bogus corner losses

## Symptom

During a Bahrain Outer Circuit session on 2026-05-31, the coaching reported:

> "You lost one point six seconds at the apex of turn 9."

for lap 4 (71.38 s per the coach log). The actual total lap delta was ~0.7 s
(second-stint lap 4 vs. reference 70.845 s). A single corner cannot account
for more time than the total lap deficit, so the coaching value was bogus.

See: `sessions/recorder_with_coach.txt` line 27, lap 4.

## Root cause

The sim was restarted mid-recording (the in-game session was reset while the
recorder stayed alive on the same track+vehicle combo). The recorder does NOT
detect a `session_time_s` regression as a session boundary, so the same
`SessionWriter` kept accumulating shards across both stints:

| rows | stint | lap_number=4 | lap_time |
|------|-------|--------------|----------|
| 17434–21077 | first stint | 4 | ~73.0 s |
| 52524–56085 | second stint | 4 | ~71.6 s |

When the second-stint lap 4 completed, `SessionWriter._write_lap_snapshot(4)`
(`writer.py:298`) merged **all accumulated shards** and filtered by
`lap_number == 4`. The resulting snapshot contained **7 206 rows from two
completely different laps** (3 644 + 3 562). The distance trace rewinds
from ~3 500 m back to 0 inside a single "lap", producing a garbled
delta-T trace.

`compare_laps` received the corrupted snapshot and computed:
- Reported total lap delta: **2.384 s** (wrong; true second-stint delta: **0.729 s**)
- Reported top loss: **turn 9, 1.567 s** (prompted the "1.6 s" utterance)
- Correct top loss (clean data): **turn 8, 0.284 s**

### The offending filter (writer.py:308)

```python
filtered = merged.filter(pc.equal(merged.column("lap_number"), lap_num))
```

`lap_number` is not unique within a session if the sim's lap counter resets.
`session_time_s` in the parquet confirms the reset: it goes from ~592 s at
row 31 244 back to ~3.6 s at row 31 245.

## Fix direction

Detect `session_time_s` going backward by more than a threshold (e.g. 30 s)
in `record.py` and close/reopen the `SessionWriter`. This keeps each physical
sim session in its own parquet so the data is never mixed, and
`_write_lap_snapshot` stays simple.

## Files

- `repro.py` — self-contained reproduction script
- `sessions/session_20260531T173205Z_bahrain-outer-circuit_lmu.parquet`
  (the triggering session; first and second stint merged in one file)
- `sessions/recorder_with_coach.txt` (coach output log)
