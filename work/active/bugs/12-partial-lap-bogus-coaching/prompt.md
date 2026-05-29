# Bug 12: Partial lap produces bogus coaching gains

## Observed symptom

```
lap-telemetry: [coach] lap completed: lap 8, track=Bahrain Outer Circuit, frames=1237, lap_time=21.64s
lap-telemetry: [coach] timing-from-parquet lap=8 parquet_read=125ms compare=125ms llm=0ms total=125ms
lap-telemetry: [coach] utterance (enqueue +8578ms): You gained 15 seconds at the apex of turn 4.
```

Bahrain Outer reference lap = 1:11.380 (71.38s). A 15-second gain on a 71-second lap
is physically impossible.

## Reproduction

Session file in repo (committed as fixture reference):
```
sessions/session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet
```
Reference lap: `product/data/reference-laps/bahrain-outer-circuit_dkr-engineering-4-elms25_time_01.11.380.parquet`
Track model:   `product/data/track-coaching/bahrain-outer-circuit_dkr-engineering-4-elms25.json`

Run `dev/tools/inspect_lap8.py` to see the raw data and reproduce the bogus compare_laps output.

```
$ python dev/tools/inspect_lap8.py
compare_laps(lap 8) top_gains:
  t4 minimum_speed: loss_s=-15.153  apex_m=2038  driver=151.9  ref=105.0
  t4 exit:          loss_s=-14.033  apex_m=2038  driver=151.9  ref=108.1
  t5 minimum_speed: loss_s=-10.711  apex_m=3047  driver=151.9  ref=99.1
```

## Root cause (two overlapping issues)

### Issue A — stale cross-lap frame inflates max(current_dist)

Lap 8 in the parquet contains one stale frame from the lap 7→8 boundary:

```
index 31257: lap_number=8, lap_time_s=-0.163, dist_m=3510.3, raw_dist=3498.7, speed=224.2
index 31258: lap_number=8, lap_time_s= 0.037, dist_m=   -0.0, raw_dist=  -0.0, speed=224.3
```

`lap_number` already incremented to 8 (telemetry cadence) but `mLapDist` had not yet
reset in the scoring data. `dist_m=3510.3` is the end-of-lap-7 position.

`compare_laps(lap_number=8)` pulls all rows where `lap_number==8`.
`max(current_dist)` = **3510.3m** (from that one stale frame).
The JS pipeline therefore resamples to 3510 bins, as if this were a full lap.

### Issue B — frozen session-end frames fill the gap

The session was stopped while lap 8 was in progress. The last ~20 frames are frozen:

```
index 32474-32493: lap_time_s=21.637, dist_m=1046.5, speed=151.9
```

The car reached 1046m (out of 3510m total) before the session ended. Turn 4 is at
2038m — **never reached in lap 8**.

After the stale frame inflates `max_dist` to 3510m, the JS pipeline has:
- Current lap: real data for bins 0–1046, then **extrapolated/clamped at 151.9 kph**
  for bins 1047–3510 (the frozen session-end speed)
- Reference lap: real corner speeds for all 3510 bins

At turn 4 (2038m): driver = 151.9 kph (fake frozen value) vs reference = 105.0 kph
(real corner minimum). Δspeed = +46.9 kph. Delta-t integration computes a fake
**-15.15-second gain** for the driver.

## Files to fix

### `product/python/lap_telemetry/coach/lap_comparator.py`

**Fix 1 — strip stale frames when filtering by lap_number** (fixes Issue A):

When `lap_number` is provided, additionally drop rows where `lap_time_s < 0`.
These are cross-lap boundary artifacts where `lap_number` already incremented
but `mLapDist` / `lap_time_s` still reflect the previous lap.

```python
if lap_number is not None:
    lap_numbers = current_table.column("lap_number").to_pylist()
    lap_times   = current_table.column("lap_time_s").to_pylist()
    mask = [ln == lap_number and lt >= 0 for ln, lt in zip(lap_numbers, lap_times)]
    current_table = current_table.filter(mask)
```

**Fix 2 — guard against partial laps** (fixes Issue B):

After filtering, check coverage. If `max(current_dist) < track_model.lap_length_m * 0.80`,
raise `PartialLapError` (or return an empty/skipped `LapComparisonFacts`) so the
caller knows not to generate a coaching utterance.

The threshold 80% (= ~2808m for Bahrain Outer) is conservative: even a lap that
aborts at turn 4 (2038m = 58%) would be caught. Any lap that crosses the
finish line normally will have dist ≥ ~3400m.

### `product/python/lap_telemetry/coach/live_fact_generator.py`

`generate_from_parquet()` should catch `PartialLapError` and log a warning instead
of passing it up:

```python
except PartialLapError as e:
    log.warning("Skipping partial lap %d: %s", lap_number, e)
    return None
```

## Files to investigate (no change expected)

- `product/python/lap_telemetry/recorder/connect.py` — the stale frame is produced
  because `lap_number` is read from telemetry (fast) while `mLapDist` is in scoring
  (slow, ~5 Hz). This is the same boundary inconsistency tracked by bug 10. The
  recorder fix (if any) belongs to bug 10b; the comparator must defend itself
  regardless.

## Tests to add

Use `sessions/session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet` as the
test fixture (or extract lap 8 rows into `dev/fixtures/coach/bahrain_outer_lap8.parquet`).

1. **Test: stale-frame stripping** — assert that after filtering to
   `lap_number=8` + `lap_time_s >= 0`, the frame with `dist_m=3510.3` is absent
   and `max(current_dist) < 1100`.

2. **Test: partial-lap guard** — assert that `compare_laps(session, ref, model,
   lap_number=8)` raises `PartialLapError` (or returns an empty result), not a
   facts object with gains > 5 seconds.

3. **Test: good lap unaffected** — assert that `compare_laps(session, ref, model,
   lap_number=5)` still returns a valid `LapComparisonFacts` with
   `|lap_time_delta_s| < 5s` and `|loss_s| < 3s` for all gains/losses.

## Acceptance

- `dev/tools/inspect_lap8.py` shows no gain > 5 seconds for lap 8.
- The test suite for the coach passes.
- A partial lap (< 80% track coverage) is silently skipped by the coaching pipeline
  with a log warning, not an utterance.
