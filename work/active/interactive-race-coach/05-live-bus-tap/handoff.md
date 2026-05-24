# Slice 05: Live Bus Tap — Handoff

## What is on disk

### New files
- `product/python/lap_telemetry/recorder/bus.py` — `LiveBus` (sync callback bus) + `QueuedBus` (threaded bounded queue with oldest-first drop)
- `product/python/lap_telemetry/coach/lap_detector.py` — `LapDetector` with `LapCompleted` and `NewLap` dataclasses, `current_lap_frames` buffer
- `product/python/lap_telemetry/coach/coach_tap.py` — `CoachTap` wires `QueuedBus` → `LapDetector`, prints debug to stderr
- `product/python/lap_telemetry/coach/live_coach.py` — CLI entry point: `python -m lap_telemetry.coach.live_coach --out-dir sessions`
- `record_with_coach.py` — project-root launcher script
- `product/python/demo_coach_slice05.py` — demo script with `--once` flag
- `dev/scripts/test_live_bus_tap.py` — Python test (39 assertions)
- `dev/scripts/test_live_bus_tap.js` — Node.js wrapper for parallel runner

### Modified files
- `product/python/lap_telemetry/recorder/record.py` — `run()` now accepts `bus: LiveBus | QueuedBus | None = None`; publishes recordable frames via `bus.publish(frame)` when bus is not None
- `package.json` — `interactive-race-coach` feature now includes `dev/scripts/test_live_bus_tap.js`

## Feature flags / config
- Bus is **opt-in**: `bus=None` (default) means zero overhead, identical behaviour to pre-slice
- `QueuedBus(maxsize=256)` is the default in `live_coach.py`; configurable at construction time

## New helpers worth knowing
- `LiveBus.subscribe(callback) → Unsubscribe` — returns an unsubscribe handle
- `QueuedBus.start()` / `QueuedBus.shutdown()` — manage the worker thread lifecycle
- `LapDetector.feed(frame)` — push frames; events fire via `on_lap_completed` / `on_new_lap` callbacks
- `LapDetector.current_lap_frames` — rolling list of frames for the lap in progress (for slice 06)
- `LapCompleted.frames` — frozen list of all frames from the completed lap (for slice 06 fact generation)

## Deferred TODOs
- No LLM or TTS integration in the bus/tap (slices 06+)
- `record_with_coach.py` is intentionally minimal — just starts recorder + coach tap
- Cross-process bus (WebSocket/HTTP) not needed for MVP

## Test status
- All 39 assertions pass: `bash scripts/test-summary.sh dev/scripts/test_live_bus_tap.js`
- `npm run build` succeeds
- Pre-existing pyarrow/numpy incompatibility in this env blocks some unrelated tests (not introduced by this slice)