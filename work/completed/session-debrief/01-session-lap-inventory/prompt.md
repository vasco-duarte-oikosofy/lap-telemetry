# Slice 01: Session Lap Inventory

## Goal

Given a recorded session (single file or rotation shards), produce a
**reusable, structured inventory of its laps** — one record per contiguous
segment, each classified as eligible or not, with the reason — and print it
from a new `lap-telemetry debrief --list` command.

This is the foundation every later slice stands on: nothing in the debrief can
be trusted until we know exactly which laps are real flying laps.

## Why this slice first

The comparison engine today filters by `lap_number`. That is wrong for a whole
session: a sim restart resets `lap_number` to 0, so
`session_20260524T141613Z_paul-ricard---3a_lmu.parquet` has segments
`0,1,2` followed by `0..21`. Filtering by `lap_number` silently concatenates
two different stints into one input.

`lap_comparator.py` also sits at 422 of the 437-line hard ceiling, so the
segment-aware refactor cannot land until its slicing helpers move out.

## User-visible result

```text
$ lap-telemetry debrief dev/sessions/session_20260524T141613Z_paul-ricard---3a_lmu.parquet --list
session : session_20260524T141613Z_paul-ricard---3a_lmu
track   : Paul Ricard - 3A
vehicle : DKR Engineering #4:ELMS25
shards  : 1   rate: 50.0 Hz   yardstick: 1:20.044

 seg  lap  frames   duration   status      reason
   0    0    9005  148:16.314  out-lap     first segment of a stint
   1    1    4236    1:24.804  eligible
   2    2    6235    1:19.882  eligible
   ...
  16   13    1198    0:21.917  in-lap      duration 0.27x the session yardstick
  17   14    5914    1:59.104  pit-lap     stopped for 8.4 s
  ...
  24   21   10838    0:00.548  incomplete  final segment of the session

19 of 25 segments eligible (17 clean). A debrief needs at least 5.
```

## Scope

### In scope

1. **Refactor first** (`refactor:` commit, no behaviour change): extract the
   table-slicing and duration helpers out of `coach/lap_comparator.py` into
   `coach/lap_table.py`, and pull the inline stale-boundary-frame filter into a
   named helper. `lap_comparator.py` must end comfortably under 400 lines.
2. `product/python/lap_telemetry/session_laps.py` — one job: enumerate and
   classify laps of a recorded session.
   - `load_session(path)` — in-memory merge of `.partN.parquet` shards in part
     order, sidecar metadata, shard count. Never writes to disk.
   - `classify_laps(table, ...)` — one `LapRecord` per contiguous segment with
     `status`, `reason`, and a `clean` flag for eligible laps.
   - `format_inventory(records, meta)` — the printable table above.
3. `lap-telemetry debrief <file> --list` wired into `cli.py`.
4. Tests: `dev/scripts/test_session_lap_inventory.py` + `.js` wrapper, added to
   `testFeatures["session-debrief"]`.

### Out of scope

- No comparison against the reference, no facts, no consistency, no LLM.
- No new columns in `LapRecord` that nothing consumes yet (no sectors, no
  fuel). Slice 03/04 add what they need.
- No changes to `summary.py`. It keeps its own formatting; the debrief owns
  its own.

## Classification rules

Order matters; the first matching rule wins:

| # | Status | Rule |
|---|---|---|
| 1 | `incomplete` | final segment of the session (recording ends mid-lap or untimed) |
| 2 | `incomplete` | distance coverage fails: segment max distance < 80% or segment min distance > 10% of the estimated lap length |
| 3 | `out-lap` | first segment of a stint (segment 0, or `lap_number` not equal to the previous segment's `lap_number` + 1) |
| 4 | `short` | frame count inconsistent with the duration by more than 2x either way |
| 5 | `invalid` | `lap_valid` column discriminates in this session (it has both values) and any frame of the segment is `False` |
| 6 | `in-lap` | duration < 0.85x the session yardstick |
| 7 | `pit-lap` | stationary (speed < 3 km/h) for at least 1.0 s anywhere in the segment |
| 8 | `pit-lap` | duration > 1.20x the session yardstick |
| 9 | `eligible` | everything else; `clean = duration <= 1.05x the fastest eligible lap` |

The **session yardstick** is the median authoritative duration of the interior
segments. It is deliberately session-relative: `--list` must work without a
reference lap, and a median survives the pit/out/in outliers.

`lap_valid` is ignored when it is constant across the session: real recordings
exist that are all-`True` including an 8896 s pit segment, and all-`False`
across valid laps.

## Steps

1. Write `prompt.md` (this file).
2. Refactor: extract helpers to `coach/lap_table.py`. Run
   `bash scripts/test-summary.sh --feature session-debrief` — green. Commit
   `refactor:`.
3. Write `dev/scripts/test_session_lap_inventory.py` first; run it and watch
   it fail.
4. Implement `session_laps.py` and the CLI. Re-run until green.
5. Add the test to `package.json` `testFeatures["session-debrief"]`.
6. Run `bash scripts/test-summary.sh --feature session-debrief` — must exit 0.
7. Verify against the real Paul Ricard session (25 segments) and the shard
   fixture test.
8. Write `handoff.md` and `learnings.md`, mark the slice ✅ in `PLAN.md`,
   commit and push.

## Acceptance

- `load_session` merges shards in numeric part order and reports the count.
- Classification on the real Paul Ricard session: 19 eligible, the 21.9 s lap
  is `in-lap`, the 119 s lap is `pit-lap`, the 4.1 s and 0.548 s tail segments
  are `incomplete`, and every segment carries a non-empty reason unless it is
  eligible.
- 17 of those 19 eligible laps are `clean` (the 1:24.8 opener and the 1:30.7
  lap are not).
- `debrief --list` exits 0, prints the inventory and the eligible count, and
  warns when fewer than five laps are eligible.
- The refactor commit changes no rendered output: the whole feature suite
  stays green before and after it.
