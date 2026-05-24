# Handoff — Slice 07: Corner-Exit Coaching

## What is on disk now

### New files
- `product/python/lap_telemetry/coach/coach_config.py` — Added `CoachMode` enum (LAP/TURN/ALL) and `CoachRunConfig` dataclass (mode + top)
- `product/python/lap_telemetry/coach/corner_exit_detector.py` — `CornerExitDetector` class with cooldown, lap tracking, track model support; `CornerExited` event dataclass
- `product/python/lap_telemetry/coach/speech_window.py` — `is_speech_window()` function using straight zones or inferred gaps
- `product/python/lap_telemetry/coach/corner_exit_prompt.py` — Prompt template for corner-exit coaching (≤20 words for top=1, ≤30 for top=3)
- `product/python/lap_telemetry/coach/live_corner_fact_generator.py` — `LiveCornerFactGenerator` class with loss thresholds and partial-lap comparison
- `dev/scripts/test_corner_exit_coaching.py` — 76 unit tests
- `dev/scripts/test_corner_exit_coaching.js` — JS wrapper for parallel runner

### Modified files
- `product/python/lap_telemetry/coach/live_fact_generator.py` — Added `top` parameter to `generate()` method; truncates losses/gains and adjusts `max_words` in constraints
- `product/python/lap_telemetry/coach/coach_tap.py` — Full rewrite to support three modes (LAP/TURN/ALL), corner-exit detection, speech window checking, and pending utterance management
- `product/python/lap_telemetry/coach/live_coach.py` — Added `--coach-mode` and `--coach-top` CLI flags; wires `CornerExitDetector` and `LiveCornerFactGenerator`
- `package.json` — Added `test_corner_exit_coaching.js` to `interactive-race-coach` feature tests

## Feature flags / configuration

- `CoachMode.LAP` (default) — after-lap summaries only, backward compatible with slice 06
- `CoachMode.TURN` — corner-exit coaching only, no lap summaries
- `CoachMode.ALL` — both corner-exit and after-lap coaching
- `CoachRunConfig.top` — number of coaching items per call (1 or 3, default 3)

## CLI usage

```bash
# Default (slice 06 behavior):
python3 record_with_coach.py --out-dir sessions

# Turn-by-turn only:
python3 record_with_coach.py --out-dir sessions --coach-mode turn

# Full coaching (both channels):
python3 record_with_coach.py --out-dir sessions --coach-mode all

# Single biggest item per call:
python3 record_with_coach.py --out-dir sessions --coach-mode all --coach-top 1
```

## Deferred TODOs

- **LiveCornerFactGenerator end-to-end testing**: The unit tests use mock LLM and no reference lap. Full end-to-end with real Barcelona data would require running the recorder with a sim. This is marked as "integration test (manual)" in the prompt spec.
- **Track model auto-loading**: Currently `CornerExitDetector.track_model` is None at creation. CoachTap needs to load it when a track is detected. This works in `live_coach.py` via the LiveFactGenerator's existing model resolver, but the `CornerExitDetector` doesn't auto-load from track name changes. Future enhancement: add track model auto-loading to CoachTap when the first frame of a new track arrives.
- **Speech window retry timing**: When a pending utterance is held because the car is in a corner, it's retried on every frame until the car enters a speech window. This could be optimized with a small timer, but YAGNI for now.
- **Dynamic mode changes during a session**: Not supported (by design). Mode is set at startup.

## Pre-existing test failures (not from this slice)

- `test_losses_delta_time.js` — T3 exit loss delta assertion fails
- `test_live_after_lap_spoken_summary.js` — T14a timing-dependent utterance check fails