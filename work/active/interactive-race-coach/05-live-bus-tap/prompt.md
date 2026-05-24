# Slice 05: Live Bus Tap

## Goal

Add a live in-process telemetry bus to the recorder loop so that each
accepted `Frame` is also published to a coach subscriber. Build a lap
detector that receives frames through the bus, detects lap boundaries,
and writes debug events. The recorder continues to write Parquet sessions
normally — the bus must not perturb recording timing or correctness.

## Architecture risk validated

Can a live in-process bus stream frames to a coach subscriber without
disturbing the 50 Hz recorder loop or Parquet session writes?

## User-visible result

A single command starts both the recorder and the coach tap in one
process, with lap boundary events printed to stderr:

```bash
python3 record_with_coach.py --out-dir sessions
```

Also available as a Python module for programmatic use:

```bash
python3 -m lap_telemetry.coach.live_coach --out-dir sessions
```

When a lap boundary is detected:

```
lap-telemetry: [coach] lap completed: lap 3, track=circuit-de-barcelona, frames=2500, lap_time=89.42s
```

When a new lap starts:

```
lap-telemetry: [coach] new lap: lap 4, track=circuit-de-barcelona
```

The recorder still writes Parquet normally — no change to session files.

## Scope

### In scope

1. **Live telemetry bus** (`lap_telemetry/recorder/bus.py`)
   - In-process callback bus: `LiveBus` class with `subscribe(callback)`
     and `publish(frame)` methods.
   - `subscribe(callback)` registers a callable that receives each
     recordable `Frame`. Returns an unsubscribe handle.
   - `publish(frame)` calls every subscribed callback synchronously inside
     the recorder's frame loop. If a callback raises, log the exception
     and continue — never let a subscriber crash the recorder.
   - Bounded-queue alternative: also provide `QueuedBus` that publishes
     to a `queue.Queue(maxsize=N)` and runs the consumer on a worker
     thread. Older frames are dropped when the queue is full. This is
     the recommended bus for coach subscribers that may be slow.
   - Thread safety: `LiveBus` is called from the recorder thread. The
     subscribe/unsubscribe list is protected by a lock. Callbacks run
     on the publisher's thread (synchronous bus) or on the worker thread
     (queued bus).

2. **Recorder integration** (`lap_telemetry/recorder/record.py`)
   - Accept an optional `bus: LiveBus | None` parameter in `run()`.
   - After `writer.append(frame)` and only for recordable frames, call
     `bus.publish(frame)`.
   - When `bus` is `None` (the default), behaviour is identical to today —
     zero overhead, no bus created.
   - This is the **only** change to the recorder module. The bus is
     opt-in and invisible when not used.

3. **Coach lap detector** (`lap_telemetry/coach/lap_detector.py`)
   - Receives frames from the bus (via a callback).
   - Detects lap boundaries: `lap_number` changes between consecutive
     frames and `lap_distance_m` drops (resets near zero).
   - Emits `LapCompleted` and `NewLap` events as dataclass objects.
   - Maintains a rolling buffer of frames for the current lap (for use
     by slice 06's fact generator).
   - `current_lap_frames: list[Frame]` — frames accumulated for the
     lap in progress.
   - On `LapCompleted`, freezes the completed lap's frames and resets
     the buffer for the next lap.
   - Event callbacks: `on_lap_completed(event)` and `on_new_lap(event)`.

4. **Coach tap orchestrator** (`lap_telemetry/coach/coach_tap.py`)
   - Wires together: `QueuedBus` → `LapDetector`.
   - Registers the lap detector as a bus subscriber.
   - Prints debug events to stderr (lap completed, new lap).
   - Provides `shutdown()` for clean teardown.
   - This is the "coach" side of the split — it knows nothing about
     recording, Parquet, or sessions. It only sees Frames from the bus.

5. **CLI entry point** (`lap_telemetry/coach/live_coach.py`)
   - `--out-dir` — Parquet session output directory (passed to recorder).
   - Starts the recorder with a `QueuedBus` attached.
   - Creates a `CoachTap` that subscribes to the bus.
   - Runs until Ctrl+C, then shuts down cleanly (bus, tap, recorder).
   - The recorder writes Parquet normally. The coach tap prints debug.

6. **Session launcher script** (`record_with_coach.py`)
   - Simple top-level script that starts both the recorder and the
     coach orchestrator in one process.
   - This is the primary way a driver starts a coached session:
     ```bash
     python3 record_with_coach.py --out-dir sessions
     ```
   - Internally creates a `QueuedBus`, wires a `CoachTap` to it,
     then calls `recorder.run()` with the bus attached.
   - The recorder writes Parquet normally. The coach tap prints
     lap events to stderr.
   - Clean Ctrl+C shutdown: stops the coach tap, then lets the
     recorder's finally-block close the writer.
   - Single command, single process, single Ctrl+C to stop.
   - PowerShell equivalent documented:
     ```powershell
     python record_with_coach.py --out-dir sessions
     ```

7. **Demo script** (`product/python/demo_coach_slice05.py`)
   - Runs the recorder with a live bus tap.
   - Similar pattern to earlier demo scripts.
   - Since we cannot connect to a real sim in CI, the demo script
     uses the `--once` flag for a quick smoke test.

### Out of scope

- LLM integration (slice 03, already done)
- TTS integration (slice 04, already done)
- Fact generation on lap completion (slice 06)
- Speech window detection (slice 06/07)
- Race engineer / fuel channels (slice 08+)
- Cross-process bus (localhost HTTP/WebSocket) — in-process is enough for MVP
- Any modification to Frame dataclass fields

## Design: LiveBus vs QueuedBus

Two bus implementations serve different use cases:

**`LiveBus`** (synchronous callback bus):
- Simplest possible implementation.
- Callbacks run on the recorder thread.
- Use for lightweight subscribers where processing is < 1 ms.
- Risk: a slow callback delays the 50 Hz loop. Use with caution.
- Acceptable for: debug printing, metric counters, simple event detection.

**`QueuedBus`** (threaded bounded queue):
- Pushes frames into a `queue.Queue(maxsize=N)`.
- A worker thread drains the queue and calls callbacks.
- Older frames are dropped when the queue is full (oldest-first drop).
- Non-blocking for the publisher: `publish()` just calls
  `queue.put_nowait()` or drops if full.
- Use for coach subscribers that may do slow work (I/O, LLM calls).
- The recommended bus for the coach tap.

For this slice, the `CoachTap` uses a `QueuedBus` because it is the
production configuration. `LiveBus` exists for simpler use cases and
testing.

## Design: lap boundary detection

Lap boundaries are detected from `Frame` fields, not from any new sim
signal. The recorder already prints "lap boundary -> lap N" by watching
`frame.lap_number` change. The `LapDetector` uses the same signal:

- **New lap:** `frame.lap_number` increases (or changes) compared to
  the previous frame.
- **Lap completed:** When a new lap starts, the *previous* lap is
  considered completed. The `LapDetector` collects the previous lap's
  frames and emits a `LapCompleted` event with:
  - `lap_number: int`
  - `track_name: str`
  - `lap_time_s: float` (last frame's `lap_time_s`)
  - `frame_count: int` (number of frames collected for that lap)
  - `frames: list[Frame]` (for use by slice 06's fact generator)

Edge cases:
- First frame ever: no `LapCompleted`, just record `current_lap`.
- Lap number goes backward (session reset): emit `NewLap` for the
  new number, discard the in-progress lap without emitting completion.
- Track name changes: treat as a new session; discard in-progress lap.

## Design: recorder integration

The change to `record.py` is minimal:

```python
def run(
    rate_hz: float = 50.0,
    once: bool = False,
    probe_timeout_s: float = 0.0,
    out_dir: Path = Path("sessions"),
    bus: LiveBus | None = None,      # <-- new optional parameter
) -> int:
```

In the recording loop, after `writer.append(frame)`:

```python
if bus is not None:
    bus.publish(frame)
```

That's it. The bus is responsible for its own threading and error
handling. The recorder just calls publish and moves on.

## Windows runtime constraints

- CLI must run from PowerShell/CMD as `python -m lap_telemetry.coach.live_coach`.
- Use `pathlib.Path` for all file paths.
- Use `threading` (not `multiprocessing`, `os.fork`, or signals beyond SIGINT).
- The bus uses `queue.Queue` (cross-platform, no native deps).
- Worker threads are daemons so they don't block process exit.
- `shutdown()` must be called explicitly for clean teardown in
  normal usage (Ctrl+C handler calls it).

## Testing

### Unit tests (no sim needed)

1. **LiveBus subscribe/publish** — create a LiveBus, subscribe a
   recording callback, publish a fake Frame, verify callback was
   called with the frame.
2. **LiveBus multiple subscribers** — subscribe two callbacks,
   publish, verify both called.
3. **LiveBus unsubscribe** — subscribe, unsubscribe, publish,
   verify callback not called.
4. **LiveBus callback exception isolation** — subscribe a callback
   that raises, subscribe a second callback, publish, verify the
   second callback was still called and the exception was logged.
5. **QueuedBus publish/consume** — publish to a QueuedBus, start
   worker, verify frame consumed by callback.
6. **QueuedBus drop when full** — set maxsize=1, publish 3 frames,
   verify middle frame was dropped (oldest dropped).
7. **LapDetector new lap** — feed frames with increasing
   `lap_number`, verify `NewLap` event emitted.
8. **LapDetector lap completed** — feed frames for lap 3, then
   start lap 4, verify `LapCompleted` for lap 3 with correct
   frame count and lap time.
9. **LapDetector track change** — change `track_name` mid-session,
   verify in-progress lap discarded without completion event.
10. **CoachTap subscribe and debug output** — create a CoachTap,
    feed frames, verify stderr contains lap boundary messages.
11. **Recorder with bus vs without bus** — run recorder loop (with
    fake frames, no sim) both with and without a bus, verify
    identical frame counts are written.

### Integration tests (manual)

12. **End-to-end with recorder** — run `python -m lap_telemetry.coach.live_coach`
    with LMU running. Verify:
    - Recorder writes Parquet normally.
    - Lap boundaries are detected and printed.
    - No frame drops in the recorder.
    This is a manual smoke test, not CI.

## Acceptance criteria

- `LiveBus` with subscribe/unsubscribe/publish, callback exception isolation.
- `QueuedBus` with bounded queue, worker thread, oldest-first drop when full.
- `LapDetector` detects lap boundaries from `frame.lap_number` changes.
- `LapDetector` collects frames for the current lap and freezes them on completion.
- `CoachTap` wires bus → detector, prints debug events.
- `record.py` accepts optional `bus` parameter and publishes recordable frames.
- `live_coach` CLI runs recorder with bus tap, prints lap events.
- `record_with_coach.py` launcher script starts recorder + coach in one command.
- Unit tests pass (`bash scripts/test-summary.sh`).
- `npm run build` succeeds (no JS changes expected, but verify no regression).
- `handoff.md` and `learnings.md` created.
- Feature tests added to `package.json` under `interactive-race-coach`.

## Non-goals

- Do not build fact generation on lap completion (slice 06).
- Do not make `record_with_coach.py` do anything beyond starting recorder + coach tap — no LLM, no TTS, no fact generation.
- Do not build LLM or TTS integration (already done in slices 03/04).
- Do not build speech window detection (slice 06/07).
- Do not modify the Frame dataclass.
- Do not add cross-process bus (WebSocket/HTTP) — in-process is sufficient.
- Do not change how the recorder writes Parquet sessions.
- Do not add fuel/race channels to Frame (slice 08).

## Definition of Done

- [ ] `bus.py` implemented with LiveBus + QueuedBus
- [ ] `lap_detector.py` implemented with LapCompleted/NewLap events
- [ ] `coach_tap.py` implemented with debug output
- [ ] `record.py` accepts optional bus parameter
- [ ] `live_coach` CLI entry point works
- [ ] `record_with_coach.py` launcher script works
- [ ] Unit tests pass
- [ ] Recorder produces identical Parquet output with and without bus
- [ ] Feature test list updated in package.json
- [ ] Full test suite passes
- [ ] Build succeeds
- [ ] `handoff.md` and `learnings.md` written