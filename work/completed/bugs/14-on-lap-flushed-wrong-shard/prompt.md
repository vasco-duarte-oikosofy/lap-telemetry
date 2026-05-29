# Bug 14: `on_lap_flushed` fires with the wrong shard after bug-12 fix

## Observed symptom

From `sessions/recorder_with_coach.txt` (session `20260529T143959Z`):

```
lap-telemetry: [coach] lap completed: lap 10, ...
lap_telemetry.coach.coach_tap: Parquet flush timeout for lap 10 — falling back to event.frames

lap_telemetry.coach.live_fact_generator: Skipping coaching for partial lap 12 (...): no frames for requested lap

lap_telemetry.coach.live_fact_generator: Skipping coaching for partial lap 13 (...): no frames for requested lap

lap_telemetry.coach.live_fact_generator: Skipping coaching for partial lap 16 (...): no frames for requested lap
```

Every lap in the session either timed out on the Parquet path (laps 10, 11, 14,
15, 17, 18) or got "no frames for requested lap" (laps 12, 13, 16). No lap used
the Parquet path successfully.

## Root cause

The bug-12 fix added this to `record.py` at the lap boundary:

```python
if frame.lap_number != last_lap:
    if writer is not None:
        writer.flush_shard()   # ← added by bug-12
    ...
    last_lap = frame.lap_number

writer.append(frame)           # ← boundary frame appended AFTER flush
```

`_completed_lap_numbers` in `SessionWriter` is populated inside `append()`:

```python
# writer.py SessionWriter.append():
if self._prev_lap_number is not None and frame.lap_number != self._prev_lap_number:
    if frame.lap_number > self._prev_lap_number:
        self._completed_lap_numbers.add(self._prev_lap_number)
```

At the moment `flush_shard()` is called from `record.py`, the boundary frame
has NOT been appended yet. Therefore `_completed_lap_numbers = {}` and
`flush_shard()` writes the correct shard (containing lap N's data) but fires
NO callback.

The first frame of lap N+1 is then appended, which sets
`_completed_lap_numbers = {N}`. Later, when the 30-second timer calls
`flush_shard()`, `on_lap_flushed(timer_shard, N)` fires — but `timer_shard`
starts with lap N+1 frames, not lap N. The coach reads it filtered to
`lap_number = N`, finds zero rows, and returns `None` ("no frames for
requested lap"). The lap either gets no coaching or falls back to
`event.frames` via a timeout.

### Exact sequence (broken)

```
1. record.py: frame.lap_number=2 ≠ last_lap=1
2. record.py: writer.flush_shard()
              → _completed_lap_numbers = {}   ← empty! no callback
              → shard_0 written: [lap-1 frames]   ← correct data, silent
3. record.py: last_lap = 2
4. record.py: writer.append(frame_lap2_boundary)
              → append() sees transition 1→2 → _completed_lap_numbers = {1}
5. ... more lap-2 frames appended ...
6. record.py: 30s timer → writer.flush_shard()
              → _completed_lap_numbers = {1} → on_lap_flushed(shard_1, 1)
              → shard_1 contains [lap-2 frames]   ← WRONG shard
              → coach reads shard_1 for lap_number=1 → 0 rows → skip
```

### Two observable failure modes

- **Timeout path** (laps 10, 11, 14, 15, 17, 18): The 30-second timer fires
  only after the Parquet-path timeout (configurable in `coach_tap.py`) expires.
  Coach waits, times out, falls back to `event.frames`. Coaching works but via
  the inferior live-buffer path.

- **Wrong-shard path** (laps 12, 13, 16): The 30-second timer fires within the
  Parquet-path timeout window. The callback fires with the wrong shard. Coach
  reads zero rows, logs "no frames for requested lap", returns `None`. No
  fallback. **No coaching given.**

## Reproduction

```powershell
python work/active/bugs/14-on-lap-flushed-wrong-shard/repro.py
```

Expected output (before fix):
```
BROKEN behaviour (current record.py):
  [boundary flush] lap 1 -> 2  (completed_laps at flush time: set())
  on_lap_flushed: lap=1  shard=...part1.parquet  rows_for_this_lap=0  <-- WRONG
```

## Fix

### `product/python/lap_telemetry/recorder/writer.py`

Add an explicit registration method so the caller can mark a lap complete
before flushing — without relying on the auto-detection inside `append()`:

```python
def lap_completed(self, lap_num: int) -> None:
    """Explicitly register lap_num as completed for the next flush_shard() call.

    Call this from record.py at every lap boundary, BEFORE flush_shard(),
    so the notification fires on the shard that contains the completed lap's
    data rather than the following shard.
    """
    self._completed_lap_numbers.add(lap_num)
```

To prevent `append()` from re-adding the same lap (and firing a second
callback on the wrong shard), track which laps have already been notified:

In `__init__`: add `self._notified_lap_numbers: set[int] = set()`

In `flush_shard()`, after firing callbacks:
```python
for lap_num in sorted(self._completed_lap_numbers):
    self._on_lap_flushed(shard_path, lap_num)
    self._notified_lap_numbers.add(lap_num)
self._completed_lap_numbers.clear()
```

In `append()`, guard the auto-detection:
```python
if frame.lap_number > self._prev_lap_number:
    if self._prev_lap_number not in self._notified_lap_numbers:
        self._completed_lap_numbers.add(self._prev_lap_number)
```

### `product/python/lap_telemetry/recorder/record.py`

Call `writer.lap_completed(last_lap)` before `writer.flush_shard()` at the
lap boundary, and skip both when `last_lap < 0` (the initial `-1 → first_lap`
transition has no completed lap to notify about):

```python
if frame.lap_number != last_lap:
    if writer is not None and last_lap >= 0:
        writer.lap_completed(last_lap)   # ← register before flush
        writer.flush_shard()
    ...
    last_lap = frame.lap_number
```

## Tests to add

### `test_on_lap_flushed_fires_on_correct_shard`

Using a `SessionWriter` with an `on_lap_flushed` spy:
1. Append 5 frames of lap 1.
2. Simulate the record.py loop with the fix: call
   `writer.lap_completed(1)` then `writer.flush_shard()`.
3. Assert `on_lap_flushed` was called exactly once for lap 1.
4. Assert the shard passed to the callback contains at least 1 row with
   `lap_number == 1`.

### `test_timer_flush_does_not_double_fire`

After the lap-boundary flush for lap 1:
1. Append 5 frames of lap 2.
2. Call `writer.flush_shard()` (simulating the 30-second timer).
3. Assert `on_lap_flushed` was NOT called again for lap 1
   (no double-fire via the auto-detection in `append()`).

### `test_no_notification_without_lap_completed`

Without calling `writer.lap_completed()`:
1. Append 5 frames of lap 1, then `flush_shard()`.
2. Assert `on_lap_flushed` was NOT called (backward-compat for callers
   that don't use the explicit registration path).

## Acceptance

- `python work/active/bugs/14-on-lap-flushed-wrong-shard/repro.py` shows
  the FIXED path: `rows_for_this_lap=5` (or whatever the frame count is)
  and "All fixed assertions passed."
- A live recording session shows coaching utterances for every cleanly
  completed lap, with no "Parquet flush timeout" messages and no
  "no frames for requested lap" messages.
- `pytest tests/` passes.

## Status

✅ Fixed — commit `ad47c65` (2026-05-29)

Two-part fix:
1. `writer.lap_completed(lap_num)` + `_notified_lap_numbers` guard ensures
   the callback fires on the correct shard (not the following timer shard).
2. `_write_lap_snapshot()` merges all shards and filters to lap N before
   passing the path to the coach — fixes the regression where a mid-lap
   timer flush caused the callback to receive only the tail of the lap.

Live test confirmed: laps 7–11 all coached via `timing-from-parquet` with
no timeouts or partial-lap skips (session `20260529T154821Z`).
