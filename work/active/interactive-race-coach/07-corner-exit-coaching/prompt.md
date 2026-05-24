# Slice 07: Corner-Exit Coaching

## Goal

Speak one targeted coaching note after selected corner exits when the car is on a straight — mid-lap, not just after lap completion. This adds low-latency event timing and anti-chatter policies on top of the after-lap summary from slice 06.

## User-visible result

During a live practice session, after exiting a corner where the driver lost significant time, the coach speaks a brief note on the ensuing straight:

> "Turn 4 minimum speed, 7 km/h lower."

The after-lap summary from slice 06 continues to fire as well. Corner-exit calls are shorter (≤ 20 words) and only fire for the worst loss per corner group, with a cooldown between calls.

## Architecture risk validated

Can the coaching pipeline analyze a partial lap (live frames up to a corner exit) and speak within seconds of exiting the corner, without disturbing the 50 Hz recorder? The answer must be yes: corner-exit events trigger on the bus worker thread, fact generation and LLM calls are async, and the speech queue drops stale utterances if a higher-priority call arrives.

## Pipeline changes

```
Recorder (50 Hz loop)
   │
   ├─→ SessionWriter (Parquet — unchanged)
   │
   └─→ QueuedBus (slice 05)
         │
         └─→ CoachTap (slice 06, enhanced)
               │
               └─→ LapDetector (slice 05)
               │     ├─ NewLap event
               │     └─ LapCompleted event
               │
               └─→ CornerExitDetector (NEW)
                     │
                     └─→ CornerExited event (NEW)
                           │ carries: corner_id, corner_name,
                           │   exit_distance_m, lap_distance_m,
                           │   lap_number, track_name
                           │
                           └─→ LiveCornerFactGenerator (NEW)
                                 │ resolves ref/model for current track
                                 │ compares partial current lap vs reference
                                 │ generates short utterance via LLM
                                 │
                                 └─→ SpeechQueue.enqueue(utterance)
                                       │
                                       └─→ TTS adapter → speaker
```

All steps after the bus publish happen on the QueuedBus worker thread — never on the 50 Hz recorder thread.

## Scope

### In scope

1. **CornerExitDetector** (`lap_telemetry/coach/corner_exit_detector.py`)
   - Receives `Frame` objects via a `feed(frame)` method (called by `CoachTap` on the bus worker thread).
   - Maintains current `lap_distance_m` and current `lap_number`.
   - Uses the `TrackCoachingModel` to determine when the car transitions from a corner zone to a straight zone.
   - Emits a `CornerExited` event when `lap_distance_m` crosses from inside a corner (per `Corner.contains()`) to outside all corners (or inside a `StraightZone`).
   - Anti-chatter: after emitting a `CornerExited` event, enforces a minimum cooldown (configurable, default 8 seconds of `session_time_s`) before emitting another. This prevents call-stacking when the car passes through a chicane.
   - Resets state on `NewLap` (lap number change).
   - Does NOT emit for corner exits on the first lap (no reference lap data yet for a new track), or before the first `LapCompleted` for a track.

2. **`CornerExited` event** (`lap_telemetry/coach/corner_exit_detector.py`)
   - `corner_id: str` — e.g. `"t4"`
   - `corner_name: str` — e.g. `"turn 4"`
   - `exit_distance_m: float` — `lap_distance_m` at the moment of exit
   - `lap_number: int`
   - `track_name: str`

3. **LiveCornerFactGenerator** (`lap_telemetry/coach/live_corner_fact_generator.py`)
   - Receives a `CornerExited` event.
   - Resolves the reference lap and track model for the track (cached from slice 06).
   - Uses `current_lap_frames` from the `LapDetector` (the rolling buffer of frames for the lap in progress) to create a partial current lap.
   - Converts these frames to a temp Parquet file (reusing `frames_to_parquet`).
   - Calls `compare_laps()` with only the partial current lap data up to a short window past the corner exit.
   - Filters the resulting `LapComparisonFacts` to only the corner that was just exited.
   - If the corner has a significant loss (loss_s > 0.1 for minimum_speed, or loss_s > 0.05 for entry/exit), calls the LLM for a short coaching note (≤ 20 words).
   - If no significant loss, skips the utterance (don't coach gains on corner exit — save it for the lap summary).
   - Returns the utterance string, or `None` if skipped.

4. **SpeechWindowChecker** (`lap_telemetry/coach/speech_window.py`)
   - Determines whether it is currently safe to speak based on the car's position relative to corner zones and straight zones.
   - `is_speech_window(distance_m: float, model: TrackCoachingModel) -> bool` — returns `True` if the distance is inside a `StraightZone` or outside all corners, AND the next corner's `s_start_m` is at least `MIN_STRAIGHT_AHEAD_M` (default 50 m) away.
   - Used by `CoachTap` to decide whether to enqueue a pending corner-exit utterance or hold it.
   - If the track model has no `straight_zones`, infers speech-safe zones from gaps between corners: any distance that is not inside a `Corner` and has ≥ 50 m to the next corner's `s_start_m`.

5. **CoachTap enhancement** (`lap_telemetry/coach/coach_tap.py`)
   - Wires `CornerExitDetector` as an additional subscriber on the bus (alongside `LapDetector`).
   - On `CornerExited`: calls `LiveCornerFactGenerator.generate()`, then checks `SpeechWindowChecker.is_speech_window()` with the current `lap_distance_m`. If safe to speak, enqueues the utterance immediately; if not safe, holds it and retries on each subsequent frame until either it's safe or a higher-priority utterance arrives (stale-drop).
   - On `LapCompleted`: existing behavior (after-lap summary, unchanged).
   - Priority: `LapCompleted` utterance takes priority over a pending `CornerExited` utterance. If a `LapCompleted` utterance arrives while a corner-exit utterance is pending, the pending one is dropped (stale-drop in `SpeechQueue`).
   - Manages `SpeechQueue` lifecycle (already exists from slice 06).

6. **Corner-exit prompt contract** (`lap_telemetry/coach/corner_exit_prompt.py`)
   - A separate prompt template for corner-exit coaching notes, constrained to ≤ 20 words.
   - Simpler than the lap-summary prompt: only the single corner's facts are included.
   - The prompt instructs the LLM to be extra concise and action-oriented: "briefly note what cost time and what to try next lap".

7. **Unit tests** (`dev/scripts/test_corner_exit_coaching.py` + `.js` wrapper)
   - CornerExitDetector: emits event on corner exit, no event mid-corner, no event on first lap, cooldown enforcement, reset on lap change.
   - CornerExited event: fields populated correctly.
   - LiveCornerFactGenerator: with a canned reference + model, generates facts for a single corner; skips when loss is below threshold; returns None when no reference/model.
   - SpeechWindowChecker: returns True in straight zone, False in corner, False when next corner < 50 m ahead; infers zones from corner gaps when model has no straight_zones.
   - CoachTap wiring: CornerExited → fact gen → (mock LLM) → (mock TTS); verifies priority (LapCompleted drops pending corner utterance).

### Out of scope

- Fuel/race-state coaching (slice 08).
- Modifying `Frame` dataclass fields.
- Modifying `compare_laps()` or `LapComparator` internals.
- Generating straight zones in the track model (that's a data-authoring task; existing models with empty `straight_zones` will use inferred zones).
- Cross-process bus or WebSocket support.
- Refactoring `compare_laps()` to accept in-memory data (still uses temp Parquet bridge).

## Design decisions

### Partial-lap comparison

At corner exit, we only have frames from the start of the lap up to the current position plus a small window beyond. `compare_laps()` reads the full reference lap but the current "lap" Parquet file only covers a portion. This is fine — `compare_laps()` compares up to `min(len(current), len(reference))` distance points. The losses/gains for corners that haven't been reached yet will simply not appear in the output. We filter to only the just-exited corner.

### Anti-chatter

Without a cooldown, the coach would speak after every corner that has a loss — that's too chatty. The 8-second cooldown (in `session_time_s`) ensures at most one corner-exit call per 8 seconds of driving. After-lap summaries are not subject to this cooldown.

### Speech window

Speaking mid-corner is unsafe — the driver is busy braking/turning. We only speak in straight zones where:
1. The car is not inside a corner zone.
2. The next corner's entry is at least 50 m ahead (gives ~1 second at 180 km/h to hear the start of the message before braking).

If the track model defines `straight_zones`, those are used directly. If not, zones are inferred from gaps between corner zones (distance between `s_end_m` of one corner and `s_start_m` of the next, minus 50 m safety margin).

### Priority and stale-drop

The `SpeechQueue` already implements stale-drop (a pending utterance is replaced by a new one). Corner-exit utterances are enqueued with the same mechanism. If a `LapCompleted` utterance arrives while a corner-exit utterance is pending (not yet playing), the pending one is dropped. This matches the real-world priority: the driver wants the lap summary more than an individual corner call that's now stale.

### Corner-exit vs after-lap

These two coaching channels coexist:
- **Corner-exit**: Short (≤ 20 words), fires mid-lap after a significant loss, only in speech-safe zones.
- **After-lap**: Longer (≤ 35 words), fires at lap completion via `LapCompleted`, no speech-window check needed (driver is typically on the start/finish straight).

The `LapCompleted` after-lap summary uses the full lap's data, while corner-exit uses only partial data up to the exit point. This means the after-lap summary may contradict a corner-exit call from the same lap (e.g., "turn 4 minimum speed 7 km/h lower" at exit, then "lost 0.3s mostly in turns 4 and 5" after the lap). This is acceptable — the corner-exit call provides immediate feedback, and the lap summary provides the big picture.

## Testing

### Unit tests (no sim needed)

1. **CornerExitDetector — emits on corner exit** — Feed frames that cross from inside a corner to outside; verify `CornerExited` fires with correct `corner_id` and distance.
2. **CornerExitDetector — no event mid-corner** — Feed frames all inside a corner; verify no event.
3. **CornerExitDetector — no event on first lap** — Before any `LapCompleted`, verify corner exits don't fire.
4. **CornerExitDetector — cooldown** — Exit two corners within 8 seconds; verify only the first fires.
5. **CornerExitDetector — reset on lap change** — Exit a corner in lap 2, then lap_number changes to 3; verify cooldown resets.
6. **LiveCornerFactGenerator — single corner** — With canned reference + model, generate facts for one corner exit; verify the utterance mentions the right corner.
7. **LiveCornerFactGenerator — below threshold** — Corner with loss_s < 0.1 → returns None.
8. **LiveCornerFactGenerator — no reference/model** — Unknown track → returns None.
9. **SpeechWindowChecker — straight zone** — In a defined straight zone → True.
10. **SpeechWindowChecker — in corner** — Inside a corner → False.
11. **SpeechWindowChecker — near next corner** — < 50 m before next corner → False.
12. **SpeechWindowChecker — inferred from corners** — Model with no straight_zones → infers from gaps.
13. **CoachTap — CornerExited → utterance** — Mock LLM/TTS, verify utterance enqueued.
14. **CoachTap — LapCompleted priority** — LapCompleted utterance replaces pending corner-exit utterance.

### Integration tests (manual)

15. **End-to-end with recorder** — Run `python3 record_with_coach.py --out-dir sessions` with LMU at Barcelona. Verify:
    - After-lap summary still fires after each completed lap.
    - After exiting a corner with a loss, a brief coaching note is spoken on the next straight.
    - No coaching notes are spoken while the car is mid-corner.
    - Cooldown prevents call-stacking in chicanes.

## Acceptance criteria

- `corner_exit_detector.py` detects corner exits from `Frame.lap_distance_m` + track model.
- `live_corner_fact_generator.py` generates per-corner utterances from partial lap data.
- `speech_window.py` determines safe-speech zones from track model.
- `corner_exit_prompt.py` provides a ≤ 20 word prompt contract.
- `coach_tap.py` wires `CornerExited` → fact gen → LLM → `SpeechQueue`.
- After-lap summaries (slice 06) continue to work alongside corner-exit calls.
- Unit tests pass (`bash scripts/test-summary.sh`).
- `npm run build` succeeds (no JS changes expected, but verify no regression).
- `handoff.md` and `learnings.md` created.
- Feature tests added to `package.json` under `interactive-race-coach`.

## Non-goals

- Do not add fuel/race-state channels (slice 08).
- Do not modify `Frame` dataclass.
- Do not modify `compare_laps()` internals.
- Do not add cross-process bus or WebSocket support.
- Do not generate or modify track model `straight_zones` data — models that lack them will use inferred zones.

## Definition of Done

- [ ] `corner_exit_detector.py` detects corner exits with cooldown
- [ ] `CornerExited` event dataclass defined
- [ ] `live_corner_fact_generator.py` generates per-corner utterances
- [ ] `speech_window.py` determines safe-speech zones
- [ ] `corner_exit_prompt.py` provides short coaching prompt
- [ ] `coach_tap.py` wires CornerExited → fact gen → LLM → SpeechQueue
- [ ] After-lap summaries still work (slice 06 regression)
- [ ] Unit tests pass
- [ ] `npm run build` succeeds
- [ ] Feature test list updated in `package.json`
- [ ] `handoff.md` and `learnings.md` written