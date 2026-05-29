# Bug 12: Partial lap data produces bogus coaching gains

## Observed symptom

```
[coach] lap completed: lap 4, frames=3941, lap_time=78.88s
[coach] timing-from-parquet lap=4  ...
[coach] utterance: You gained 14 seconds at the apex of turn 1.

[coach] lap completed: lap 7, frames=3635, lap_time=72.62s
[coach] timing-from-parquet lap=7  ...
[coach] utterance: You gained 14 seconds at the apex of turn 1.

[coach] lap completed: lap 8, frames=1237, lap_time=21.64s
[coach] timing-from-parquet lap=8  ...
[coach] utterance: You gained 15 seconds at the apex of turn 4.
```

Bahrain Outer reference = 1:11.380 (71.4s, track = 3509m). Gains of 14–15 seconds
are physically impossible on a 71-second lap.

Session file: `sessions/session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet`

## Root cause — two different partial-lap scenarios

Both share the same underlying flaw: `compare_laps()` receives incomplete lap data
and silently extrapolates, producing phantom gains.

### Scenario A — tail-partial (laps 4 and 7)

`_FLUSH_INTERVAL_S = 30.0` in `record.py`. Bahrain Outer laps are ~71s.

Timeline for lap 4 (79s):
1. Lap 3 ends → lap 4 starts. Buffer accumulates lap 4 frames.
2. **Flush at T+30s** into lap 4: buffer (first ~30s of lap 4) is written as shard N.
   `_completed_lap_numbers = {3}` → `on_lap_flushed(shard N, 3)` fires. Buffer resets.
3. More lap 4 frames accumulate from ~1500m onwards.
4. Lap 4 ends (lap 5 starts). `_completed_lap_numbers = {4}`.
5. **Next flush** (≤ 30s later): shard N+1 is written with only the **tail** of lap 4
   (frames since step 2's flush, i.e. `lap_time_s >= ~30s`, starting at ~1500m).
   `on_lap_flushed(shard N+1, 4)` fires.
6. Coach reads shard N+1 → `compare_laps(shard, ref, model, lap_number=4)`.
   Filtered data: `dist=[~1500m .. 3510m]`, `lap_time_s=[~30s .. 78.88s]`.

Bins 0–1499m are clamped to `lap_time_s ≈ 30s`. Reference has `lap_time_s ≈ 0–30s`
at those same bins. Delta_t at 0m = `(30s − 0s) × 1000 = +30 000 ms`. It falls
across the first half of the track. At turn 1 (739m), delta drops from 30s to ~16s
— a phantom `loss_s ≈ −14s` for every corner in the first half.

**Reproduced** by simulating the shard cut:
```
# lap 4 tail (lap_time_s >= 30s):  loss_s=-13.803 at t1 minimum_speed
# lap 7 tail (lap_time_s >= 30s):  loss_s=-13.803 at t1 minimum_speed  ← same number
```
The `driver=94.1–95.1 kph` at turn 1 apex is the clamped speed from ~1500m
(the car's speed when recording resumed), not the real turn 1 speed.

### Scenario B — head-partial (lap 8)

The session was stopped while lap 8 was in progress. The car only reached 1046m
(turn 4 is at 2038m — never reached). Additionally, one stale cross-lap frame
at the start of lap 8 carries `dist_m=3510.3m, lap_time_s=-0.163` from the end
of lap 7.

`max(current_dist)` = 3510m (from the stale frame). The JS pipeline resamples to
3510 bins. Bins 1047–3510 are filled with the frozen session-end speed (151.9 kph).
Reference has real corner speeds (105 kph at turn 4). Phantom gain: −15s at turn 4.

**Reproduced** directly:
```
# lap 8 (with stale frame): loss_s=-15.153 at t4 minimum_speed
# lap 8 (stale stripped):   loss_s=-15.153 at t4 minimum_speed  ← still wrong
```
Stripping the stale frame doesn't fix scenario B alone — the frozen frames
at the end still extrapolate the wrong speed.

## Detection: both scenarios share the same signal

After filtering to `lap_number` and stripping stale frames (`lap_time_s < 0`):

| Scenario | `min(dist)` | `max(dist)` | Failure |
|---|---|---|---|
| Full lap | ≈ 0–10m | ≈ 3510m | — |
| Tail-partial (A) | ≈ 1500m | ≈ 3510m | min too high |
| Head-partial (B) | ≈ 0m | ≈ 1046m | max too low |

**Guard condition** (two checks, both must pass):
```python
TRACK_START_FRAC = 0.10   # data must start within first 10% of track
TRACK_END_FRAC   = 0.80   # data must reach at least 80% of track

if min(current_dist) > track_model.lap_length_m * TRACK_START_FRAC:
    raise PartialLapError("lap starts mid-track (tail-partial shard)")
if max(current_dist) < track_model.lap_length_m * TRACK_END_FRAC:
    raise PartialLapError("lap ends mid-track (session-end or head-partial)")
```

## Files to fix

### `product/python/lap_telemetry/recorder/record.py`

**Root fix for Scenario A**: trigger a shard flush at every lap boundary so the
ENTIRE completed lap is always in one shard, not split across two.

```python
if frame.lap_number != last_lap:
    writer.flush_shard()          # <-- flush before changing lap context
    last_lap = frame.lap_number
```

This ensures the shard passed to `on_lap_flushed(shard, N)` always contains the
complete data from the start of lap N to its finish line crossing — regardless of
where the 30-second timer lands.

### `product/python/lap_telemetry/coach/lap_comparator.py`

**Defensive guard** (fixes both scenarios, provides protection even if record.py
is patched or shards are read from elsewhere):

1. After filtering by `lap_number`, strip stale frames:
   ```python
   # drop cross-lap boundary artifacts: high dist, negative lap_time_s
   mask = [ln == lap_number and not (lt < 0 and ld > track_model.lap_length_m * 0.5)
           for ln, lt, ld in zip(lap_numbers, lap_times, lap_dists)]
   ```

2. Check coverage:
   ```python
   if min(current_dist) > track_model.lap_length_m * 0.10:
       raise PartialLapError(f"lap starts at {min(current_dist):.0f}m (tail-partial)")
   if max(current_dist) < track_model.lap_length_m * 0.80:
       raise PartialLapError(f"lap ends at {max(current_dist):.0f}m (head-partial)")
   ```

### `product/python/lap_telemetry/coach/live_fact_generator.py`

Catch `PartialLapError` in `generate_from_parquet()` and log a warning instead of
producing a coaching utterance.

## Files to investigate (no change expected)

- `product/python/lap_telemetry/recorder/writer.py` — `on_lap_flushed` fires with
  the shard path that was just written. The path is correct; the data in the shard
  is what's incomplete. Fix is in `record.py` (flush at lap boundary).

## Reproduction script

`dev/tools/inspect_lap8.py` — reproduces both scenarios from the merged session
parquet. The shard-cut scenario is simulated by filtering `lap_time_s >= 30`.

Run: `python dev/tools/inspect_lap8.py`

Expected output after fix:
- Lap 4 full: largest gain ≈ −0.23s (not 14s)
- Lap 7 full: largest gain ≈ −0.10s (not 14s)
- Lap 8: `PartialLapError` raised, no utterance generated

## Tests to add

1. **test_tail_partial**: filter a known full-lap parquet to `lap_time_s >= 30`
   → assert `compare_laps` raises `PartialLapError` (min_dist too high).

2. **test_head_partial**: use lap 8 from the session file
   → assert `compare_laps` raises `PartialLapError` (max_dist too low).

3. **test_full_lap_unaffected**: lap 5 or 6 from the session file
   → assert `compare_laps` returns valid facts with `|loss_s| < 3s`.

4. **test_lap_boundary_flush**: simulate `record.py` lap boundary → verify
   `flush_shard()` is called at the lap crossing so the shard contains the
   complete completed lap.

## Acceptance

- `dev/tools/inspect_lap8.py` shows no gain > 5s for laps 4, 7, or 8.
- Partial laps are logged as warnings and produce no utterance.
- A complete lap (5 or 6) still produces correct sub-second coaching.
