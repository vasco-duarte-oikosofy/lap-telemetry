# Bug 07 — Design Options: Flawless Recording & Non-Blocking Voicing

## Problem statement

Two hard requirements:

1. **Flawless recording** — every frame must reach the Parquet file, zero drops.
2. **Non-blocking voicing** — the coaching pipeline must never block frame
   ingestion or cause frame drops.

### Current architecture

```
recorder thread (50 Hz)          QueuedBus worker thread
       │                                │
       ├──► writer.append(frame)        ├──► LapDetector._on_frame()
       ├──► bus.publish(frame) ──►────► │       │
       │                                │       ├──► _on_lap_completed()
       │                                │       │       │
       │                                │       │       ├──► frames_to_parquet()  (~100ms)
       │                                │       │       ├──► compare_laps()        (~200ms)
       │                                │       │       └──► LLM call             (~5–50s)
       │                                │       │
       │   ← frames pile up here ──────│◄── blocked ~5–50s
       │   ← queue drops oldest ────────│
```

The recorder publishes frames to both `SessionWriter` (on the recorder thread)
and `QueuedBus` (single worker thread). `SessionWriter` never drops frames —
it buffers in memory and flushes shards. But `QueuedBus` has `maxsize=256`
and drops oldest when full. When `_on_lap_completed` blocks for 5–50 seconds
(fact generation + LLM/TTS), the queue fills in ~5s at 50 Hz and starts
dropping frames.

**Result:** The `LapCompleted.frames` buffer the coach uses is missing up to
21% of frames (842 of 3935 in the observed case). This produces inflated
loss values ("over three seconds at turn one" when the actual loss was 0.235s).

### Related: Bug 08 (data source mismatch)

`compare.html` reads the full session Parquet written by `SessionWriter`.
The coach reads `LapCompleted.frames` from the queue. These diverge:
the Parquet is complete; the bus buffer is incomplete. Same JS pipeline code,
different data → coach and UI can never agree.

---

## Option A: Thread-per-event (decouple coach from bus worker)

### Architecture

Move `_on_lap_completed` and `_on_corner_exited` off the bus worker thread
onto a `ThreadPoolExecutor(max_workers=1)`. The bus worker calls
`submit()` and returns immediately — it never blocks.

```
recorder thread               bus worker thread              coach thread pool
     │                              │                              │
     ├──► writer.append(frame)      │                              │
     ├──► bus.publish(frame) ─►────│                              │
     │                              ├──► LapDetector._on_frame()  │
     │                              │       │                      │
     │                              │       └──► submit() ──►────│
     │                              │            (non-blocking)   ├──► frames_to_parquet()
     │                              │                              ├──► compare_laps()
     │                              │                              └──► utterance_fn()
     │                              │
     │   ← bus worker stays free ───│   drains frames in ~0.2ms each
```

### Changes

| File | Change |
|---|---|
| `coach_tap.py` | Add `ThreadPoolExecutor(1)`. `_on_lap_completed` and `_on_corner_exited` submit to the pool instead of running inline. Add `shutdown()` joins the pool. |
| No other files change. |

### Pseudo-diff

```python
# coach_tap.py — _on_lap_completed becomes a thin submit

class CoachTap:
    def __init__(self, ...):
        ...
        self._pool = ThreadPoolExecutor(max_workers=1)

    def _on_lap_completed(self, event: LapCompleted) -> None:
        """Submit lap analysis to the thread pool (non-blocking)."""
        future = self._pool.submit(self._analyze_lap, event)
        future.add_done_callback(self._on_lap_result)

    def _analyze_lap(self, event: LapCompleted) -> str | None:
        """Heavy work: fact generation + utterance (runs on pool thread)."""
        # ... existing _on_lap_completed logic, minus speech queue enqueue ...
        return utterance

    def _on_lap_result(self, future) -> None:
        """Callback: enqueue utterance to speech queue on main thread."""
        try:
            utterance = future.result()
        except Exception:
            log.exception("Lap analysis failed")
            return
        if utterance and self._speech_queue:
            self._speech_queue.enqueue(utterance)

    def shutdown(self) -> None:
        ...
        self._pool.shutdown(wait=True)
```

Same pattern for `_on_corner_exited`.

### Tests

| # | Test | What it verifies |
|---|---|---|
| A1 | `test_bus_worker_never_blocks_on_lap` | Publish 500 frames to `QueuedBus(maxsize=256)`. Simulate a lap-completed callback that sleeps for 2s. Verify that all 500 frames are published without drops (the bus worker drains them while the lap analysis runs on the pool thread). |
| A2 | `test_lap_analysis_runs_on_pool_thread` | Submit a lap analysis via `CoachTap`. Assert the result callback fires on a different thread than the bus worker. |
| A3 | `test_lap_completed_produces_utterance` | Existing integration test — verify the thread-pool refactor doesn't break the end-to-end path from `LapCompleted` event → utterance string. Uses template mode to avoid LLM dependency. |
| A4 | `test_corner_exit_runs_on_pool_thread` | Same as A2 but for `CornerExited` events. |
| A5 | `test_coach_tap_shutdown_waits_for_pending_analysis` | Start an analysis, call `shutdown()`, verify it waits for the analysis to complete (not killed mid-way). |
| A6 | `test_sequential_laps_are_serialized` | Two `LapCompleted` events submitted rapidly. With `max_workers=1`, the second should wait for the first to finish. Verify utterances arrive in order. |
| A7 | `test_mode_off_skips_thread_pool` | `--coach-mode off` should not start the pool thread at all. |

### Strengths

- **Minimal change** — ~30 lines in `coach_tap.py`, no other files
- **Fixes frame drops** — bus worker never blocks, no queue overflow
- **Flawless recording** — `SessionWriter` is on the recorder thread, unaffected
- **Low risk** — existing tests are structural; the pool is transparent

### Weaknesses

- **Bug 08 not fixed** — coach still reads `event.frames` (bus-delivered), not the session Parquet. If there were frame drops *before* this fix (e.g. sim hiccups), coach data ≠ compare.html data. After this fix, the bus worker drains fast enough that drops are exceedingly unlikely in practice, but the architectural mismatch remains.
- **Latency unchanged** — the LLM/template call still blocks a pool thread for 5–50s. The speech queue + speech window handle timing, so this is fine for user experience, but the pipeline is still serial per event.
- **`LapCompleted.frames` still allocated** — the event carries a list of all frames for the lap, which is memory that lives until the analysis completes.

---

## Option B: Read from Session Parquet (fixes Bug 07 + Bug 08)

### Architecture

After a lap completes, instead of converting `event.frames` from the bus
buffer to a temp Parquet, wait for `SessionWriter` to flush the completed
lap's data to disk, then read the session Parquet. Coach data = compare.html
data, always.

```
recorder thread               bus worker thread              coach thread pool
     │                              │                              │
     ├──► writer.append(frame)      │                              │
     ├──► writer.flush_shard()      │                              │
     ├──► bus.publish(frame) ─►────│                              │
     │                              ├──► LapDetector._on_frame()  │
     │                              │       │                      │
     │                              │       └──► submit() ──►────│
     │                              │                              │
     │                              │                     ┌─── wait for writer
     │                              │                     │    to flush lap N
     │                              │                     ├──► read session.parquet
     │                              │                     ├──► filter to lap N rows
     │                              │                     ├──► compare_laps()
     │                              │                     └──► utterance_fn()
```

### Changes

| File | Change |
|---|---|
| `coach_tap.py` | Add `ThreadPoolExecutor(1)`. Submit analysis to pool (same as Option A). |
| `writer.py` (SessionWriter) | Add `on_lap_flushed` callback hook. When `flush_shard()` writes a shard containing a completed lap number, fire the callback with `(parquet_path, lap_number)`. |
| `live_fact_generator.py` | New method `generate_from_parquet(parquet_path, lap_number, ...)` that reads a specific lap from an existing Parquet instead of converting `event.frames`. |
| `lap_comparator.py` | Add `lap_number` filter parameter: read the Parquet, filter to the specified `lap_number`, then compare against the reference. |
| `coach_tap.py` | `_on_lap_completed` waits for the `on_lap_flushed` callback (via `threading.Event` or `Future`), then calls `generate_from_parquet()` instead of `generate()`. |
| `record.py` | Wire the `on_lap_flushed` callback from `SessionWriter` to the bus or coach tap. |

### Lap-flush signalling

The key coordination point: the coach needs to know *when* the session
Parquet is ready for a given lap number. Two sub-options:

**B1: Event-based** — `SessionWriter.flush_shard()` checks if any lap
number in the current shard buffer has changed (e.g. lap 13 → lap 14),
and fires a callback `(parquet_path, completed_lap_number)` if so. The
coach tap listens for this event.

```python
# writer.py
class SessionWriter:
    def __init__(self, ..., on_lap_flushed: Callable[[Path, int], None] | None = None):
        self._on_lap_flushed = on_lap_flushed

    def flush_shard(self) -> None:
        ...
        # After writing, check if a lap boundary crossed
        completed_laps = self._detect_completed_laps()
        for lap_num in completed_laps:
            if self._on_lap_flushed:
                self._on_lap_flushed(path, lap_num)
```

**B2: Poll-based** — The coach thread sleeps briefly and checks whether the
session Parquet file has been updated with the target lap number. Simpler
but less elegant.

**Recommendation:** B1 (event-based) — it's cleaner and deterministic.

### Tests

All Option A tests (A1–A7) plus:

| # | Test | What it verifies |
|---|---|---|
| B1 | `test_session_writer_fires_lap_flushed` | Feed frames for lap 5, then lap 6. Verify `on_lap_flushed` fires with `(path, 5)` when the shard containing the lap 5→6 transition is flushed. |
| B2 | `test_compare_laps_lap_number_filter` | Create a Parquet with laps 5, 6, 7. Call `compare_laps(path, ref, model, lap_number=6)`. Verify the resulting facts use only lap 6 data. |
| B3 | `test_generate_from_parquet_uses_complete_data` | Record a known session, flush it. Call `generate_from_parquet(session_path, lap_number=N, ...)`. Verify frame count matches the Parquet (not the bus buffer). |
| B4 | `test_coach_waits_for_parquet_before_analysis` | Simulate a `LapCompleted` event. Verify the coach thread waits for `on_lap_flushed` before starting analysis (e.g. analysis doesn't start until 1s after the event, matching the flush). |
| B5 | `test_parquet_data_matches_compare_html` | End-to-end: record a full session, run the coach pipeline, run compare.html's JS pipeline on the same Parquet. Verify the coach's facts match compare.html's facts exactly (same delta values, same corners). |
| B6 | `test_lap_flush_timeout_falls_back_to_frames` | If `on_lap_flushed` never fires (e.g. flush interval misconfigured), the coach should time out after N seconds and fall back to using `event.frames` (the old path). Verify this fallback works. |
| B7 | `test_corner_exit_uses_live_frames` | Corner exits happen mid-lap, so they can't wait for a Parquet flush. Verify `LiveCornerFactGenerator.generate()` still uses `current_lap_frames` from the `LapDetector` buffer. |

### Strengths

- **Fixes both bugs** — frame drops (Bug 07) AND data source mismatch (Bug 08)
- **Coach data = compare.html data** — always, deterministically
- **Flawless recording** — `SessionWriter` on recorder thread, never drops
- **Non-blocking voice** — analysis on pool thread, bus worker free

### Weaknesses

- **More structural change** — `SessionWriter` needs a callback, `compare_laps`
  needs lap filtering, `LiveFactGenerator` needs a new method, `record.py`
  needs wiring
- **Slight latency increase** — must wait for `flush_shard()` to write to disk
  before starting analysis. Shard flush is triggered by `_FLUSH_INTERVAL_S`
  (5s) or explicitly at lap boundaries. Worst case: 5s added latency.
- **Corner exits still use live buffer** — mid-lap events can't wait for a
  Parquet flush, so `LiveCornerFactGenerator` continues using
  `LapDetector.current_lap_frames`. This is acceptable because: (a) the
  corner exit window is small (~150m), (b) the bus worker drain time is
  ~0.2ms per frame so the buffer stays current, (c) corner exit facts are
  directional hints, not the authoritative lap summary.
- **`flush_shard` timing** — the shard flush must happen after the lap boundary
  frame is written. The recorder calls `flush_shard()` when a timer fires,
  not immediately on lap boundary. There may be a 1–5s delay between the
  lap completing and the shard being on disk.

---

## Option C: Dual-path (Parquet for after-lap, live buffer for corner-exit)

### Architecture

The end-state architecture: after-lap summaries always read from the session
Parquet (like Option B). Corner-exit notes use the live frame buffer (fast,
low-latency, small window). Both analysis paths run on the thread pool.

```
                    AFTER-LAP PATH                         CORNER-EXIT PATH
recorder              coach thread pool                    coach thread pool
  │                        │                                      │
  ├──► writer.append(f)   │                                      │
  ├──► flush_shard()      │                                      │
  ├──► bus.publish(f) ──► LapDetector._on_frame()               │
  │                        │                                      │
  │                  _on_lap_completed()                     _on_corner_exited()
  │                        │                                      │
  │                        ├──► wait for SessionWriter          ├──► use live frames
  │                        │    to flush lap N                  │    (LapDetector buffer)
  │                        ├──► read session.parquet             │
  │                        ├──► filter to lap N rows             ├──► frames_to_parquet()
  │                        ├──► compare_laps()                    │    (corner window, ~150m)
  │                        └──► utterance_fn()                   └──► utterance_fn()
```

### Changes

Same as Option B, plus:

| File | Change |
|---|---|
| All Option B changes. | |
| `coach_tap.py` | `_on_corner_exited` uses `LapDetector.current_lap_frames` (live buffer) and runs on the pool thread. This is already the case — just making it explicit. |
| `live_corner_fact_generator.py` | No change — already uses `current_lap_frames`. Just needs to run on the pool thread. |

### Tests

All Option A and Option B tests, plus:

| # | Test | What it verifies |
|---|---|---|
| C1 | `test_corner_exit_uses_live_buffer_not_parquet` | After a corner exit event, verify that `LiveCornerFactGenerator.generate()` receives frames from `LapDetector.current_lap_frames`, not from the session Parquet. |
| C2 | `test_after_lap_uses_parquet_not_live_buffer` | After a lap-completed event, verify that `LiveFactGenerator.generate_from_parquet()` reads the session Parquet, not `event.frames`. |
| C3 | `test_parallel_corner_and_lap_analysis` | Simulate a corner exit happening during lap analysis. Verify both run concurrently on the pool (neither blocks the other). |
| C4 | `test_lap_analysis_uses_complete_parquet_during_corner_exit` | While a corner exit is being analyzed from live frames, a lap analysis reads from the Parquet. Verify the Parquet data is complete (all frames for that lap present). |

### Strengths

- **Both bugs fully fixed** — no frame drops, no data mismatch
- **After-lap data is authoritative** — always matches compare.html
- **Corner exits are fast** — use live buffer (sub-second latency)
- **Fully non-blocking** — everything runs on the pool thread

### Weaknesses

- **Most code to change** — Options A + B changes, plus clarity about the two paths
- **Same flush latency as Option B** — after-lap summaries wait for Parquet flush
- **Corner exits can still disagree with compare.html** — they use live frames.
  But this is deliberate: corner exits need sub-second latency and operate on
  a ~150m window, so data completeness is less critical
- **Two data paths to maintain** — after-lap reads Parquet, corner-exit reads
  live buffer. Test surface is larger.

---

## Comparison table

| Aspect | Option A | Option B | Option C |
|---|---|---|---|
| Fixes frame drops (Bug 07) | ✅ | ✅ | ✅ |
| Fixes data mismatch (Bug 08) | ❌ | ✅ | ✅ |
| Lines of code changed | ~30 | ~80 | ~120 |
| Risk | Low | Medium | Medium |
| Flawless recording | ✅ | ✅ | ✅ |
| Non-blocking voice | ✅ | ✅ | ✅ |
| After-lap data source | `event.frames` | Session Parquet | Session Parquet |
| Corner-exit data source | `event.frames` | `event.frames` | Live buffer |
| Latency added | 0 | 0–5s (wait for flush) | 0–5s (after-lap only) |
| New test count | 7 | 14 | 18 |

## Recommendation

**Start with Option A, then build toward Option C.**

Option A is deployable in a single focused slice. It gives you both hard
requirements — flawless recording and non-blocking voice — with minimal
risk. Bug 08 (data mismatch) is real but cosmetic in practice: after
Option A, the bus worker drains in ~0.2ms per frame, so queue overflow
is vanishingly unlikely. The architectural mismatch (bus data vs. Parquet
data) can be addressed in a follow-up slice when the flush-signalling
mechanism is ready.

Option C is the end state. If you want to fix both bugs in one slice,
Option B is the sweet spot: same Parquet-based after-lap data, corner-exit
still uses live frames (acceptable trade-off), and you get the data
mismatch fix without the dual-path complexity.