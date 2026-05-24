# Slice 07: Corner-Exit Coaching

## Goal

Speak one targeted coaching note after selected corner exits when the car is on a straight — mid-lap, not just after lap completion. This adds low-latency event timing and anti-chatter policies on top of the after-lap summary from slice 06. The driver controls **when** coaching fires (lap-only, turn-by-turn, or both) and **how many** coaching points per call (the single biggest item, or the top 3) via CLI flags.

## User-visible result

Starting the recorder with coach is now configurable:

```bash
# Only after-lap summaries (slice 06 default, top 3 losses):
python3 record_with_coach.py --out-dir sessions

# Only after-lap summaries, single biggest item:
python3 record_with_coach.py --out-dir sessions --coach-mode lap --coach-top 1

# Only turn-by-turn coaching (no lap summary):
python3 record_with_coach.py --out-dir sessions --coach-mode turn

# Both turn-by-turn and after-lap (full coaching):
python3 record_with_coach.py --out-dir sessions --coach-mode all

# Both, top 3 per call:
python3 record_with_coach.py --out-dir sessions --coach-mode all --coach-top 3
```

During a live practice session with `--coach-mode all`:

> *(exiting turn 4, on the straight)* "Turn 4 minimum speed, 7 km/h lower."

> *(after lap completion)* "Lost three tenths mostly in turns 4 and 5. Minimum speed was 7 km/h lower through turn 4, exit throttle later in turn 5. Next lap, protect entry speed there."

With `--coach-top 1`, each call says only the single most important item.

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
               ├─→ LapDetector (slice 05)
               │     ├─ NewLap event
               │     └─ LapCompleted event  ──→  if coach_mode in (lap, all):
               │                                     LiveFactGenerator → LLM → SpeechQueue
               │                                        (top N losses/gains)
               │
               └─→ CornerExitDetector (NEW)
                     │
                     └─→ CornerExited event  ──→  if coach_mode in (turn, all):
                                                     LiveCornerFactGenerator → LLM → SpeechQueue
                                                        (top N losses for this corner)
```

All steps after the bus publish happen on the QueuedBus worker thread — never on the 50 Hz recorder thread.

## Scope

### In scope

1. **CoachMode enum** (`lap_telemetry/coach/coach_config.py`)
   - `CoachMode` enum with values `LAP`, `TURN`, `ALL`.
   - `CoachConfig` dataclass holding `mode: CoachMode` and `top: int` (number of coaching items per call, default 3).
   - CLI flags `--coach-mode lap|turn|all` (default: `lap`) and `--coach-top 1|3` (default: `3`).
   - Backward compatible: `--coach-mode lap --coach-top 3` reproduces the slice 06 default (after-lap summary, top 3 items).

2. **CornerExitDetector** (`lap_telemetry/coach/corner_exit_detector.py`)
   - Receives `Frame` objects via a `feed(frame)` method (called by `CoachTap` on the bus worker thread).
   - Maintains current `lap_distance_m` and current `lap_number`.
   - Uses the `TrackCoachingModel` to determine when the car transitions from inside a corner zone to outside.
   - Emits a `CornerExited` event when `lap_distance_m` crosses from inside a corner (per `Corner.contains()`) to outside all corners (or inside a `StraightZone`).
   - Anti-chatter: after emitting a `CornerExited` event, enforces a minimum cooldown (configurable, default 8 seconds of `session_time_s`) before emitting another. This prevents call-stacking when the car passes through a chicane.
   - Resets state on `NewLap` (lap number change).
   - Does NOT emit for corner exits on the first lap (no reference lap data yet for a new track), or before the first `LapCompleted` for a track.

3. **`CornerExited` event** (`lap_telemetry/coach/corner_exit_detector.py`)
   - `corner_id: str` — e.g. `"t4"`
   - `corner_name: str` — e.g. `"turn 4"`
   - `exit_distance_m: float` — `lap_distance_m` at the moment of exit
   - `lap_number: int`
   - `track_name: str`

4. **LiveCornerFactGenerator** (`lap_telemetry/coach/live_corner_fact_generator.py`)
   - Receives a `CornerExited` event.
   - Resolves the reference lap and track model for the track (cached from slice 06).
   - Uses `current_lap_frames` from the `LapDetector` (the rolling buffer of frames for the lap in progress) to create a partial current lap.
   - Converts these frames to a temp Parquet file (reusing `frames_to_parquet`).
   - Calls `compare_laps()` with only the partial current lap data up to a short window past the corner exit.
   - Filters the resulting `LapComparisonFacts` to only the corner that was just exited.
   - Takes the top `N` losses (where `N` = `CoachConfig.top`) for that corner.
   - If the corner has a significant loss (loss_s > 0.1 for minimum_speed, or loss_s > 0.05 for entry/exit), calls the LLM for a short coaching note.
   - For corner-exit calls, the LLM prompt constrains to ≤ 20 words when `top=1`, ≤ 30 words when `top=3`.
   - If no significant loss, skips the utterance (don't coach gains on corner exit — save it for the lap summary).
   - Returns the utterance string, or `None` if skipped.

5. **Top-N filtering in LiveFactGenerator** (`lap_telemetry/coach/live_fact_generator.py`, enhanced)
   - The `LiveFactGenerator` already calls `compare_laps()` which returns `LapComparisonFacts` with `top_losses[:3]` and `top_gains[:3]`. Enhance it to respect `CoachConfig.top`: when `top=1`, truncate facts to only the single worst loss (and single best gain if any).
   - The LLM prompt should adapt its word limit based on `top`: ≤ 35 words for `top=3`, ≤ 20 words for `top=1`.

6. **SpeechWindowChecker** (`lap_telemetry/coach/speech_window.py`)
   - Determines whether it is currently safe to speak based on the car's position relative to corner zones and straight zones.
   - `is_speech_window(distance_m: float, model: TrackCoachingModel) -> bool` — returns `True` if the distance is inside a `StraightZone` or outside all corners, AND the next corner's `s_start_m` is at least `MIN_STRAIGHT_AHEAD_M` (default 50 m) away.
   - Used by `CoachTap` to decide whether to enqueue a pending corner-exit utterance or hold it.
   - If the track model has no `straight_zones`, infers speech-safe zones from gaps between corners: any distance that is not inside a `Corner` and has ≥ 50 m to the next corner's `s_start_m`.

7. **CoachTap enhancement** (`lap_telemetry/coach/coach_tap.py`)
   - Accepts a `CoachConfig` (mode + top) at construction time.
   - When `mode == LAP`: only wires `LapDetector` → `LiveFactGenerator`. `CornerExitDetector` is not subscribed to the bus. This is the default and reproduces slice 06 behavior exactly.
   - When `mode == TURN`: only wires `CornerExitDetector` → `LiveCornerFactGenerator`. `LapDetector` is wired but `LapCompleted` events do not trigger utterance generation.
   - When `mode == ALL`: wires both channels. `LapCompleted` → `LiveFactGenerator`. `CornerExited` → `LiveCornerFactGenerator`.
   - On `CornerExited`: calls `LiveCornerFactGenerator.generate()`, checks `SpeechWindowChecker` with current `lap_distance_m`. If safe to speak, enqueues immediately; otherwise holds and retries on subsequent frames.
   - Priority: `LapCompleted` utterance supersedes a pending `CornerExited` utterance (stale-drop in `SpeechQueue`).
   - Both `LiveFactGenerator` and `LiveCornerFactGenerator` receive `CoachConfig.top` to control how many coaching items to include in the LLM prompt.

8. **CLI flags** (`lap_telemetry/coach/live_coach.py`)
   - `--coach-mode lap|turn|all` — when to speak. Default: `lap`.
   - `--coach-top 1|3` — how many coaching items per call. Default: `3`.
   - These are passed to `CoachConfig` and through to `CoachTap`.

9. **Corner-exit prompt contract** (`lap_telemetry/coach/corner_exit_prompt.py`)
   - A separate prompt template for corner-exit coaching notes.
   - Word limit scales with `top`: ≤ 20 words for `top=1`, ≤ 30 words for `top=3`.
   - Only the exited corner's facts are included in the prompt.
   - Instructs the LLM to be concise and action-oriented.

10. **Unit tests** (`dev/scripts/test_corner_exit_coaching.py` + `.js` wrapper)
    - CoachMode enum and CoachConfig defaults.
    - CornerExitDetector: emits on corner exit, no event mid-corner, no event on first lap, cooldown enforcement, reset on lap change.
    - CornerExited event: fields populated correctly.
    - LiveCornerFactGenerator: single corner with loss → utterance; below threshold → None; no reference → None.
    - Top-N filtering: `top=1` truncates to worst loss only; `top=3` includes up to 3.
    - SpeechWindowChecker: True in straight zone, False in corner, False near next corner, inferred from corner gaps.
    - CoachTap wiring: `mode=lap` only fires after-lap; `mode=turn` only fires at corner exit; `mode=all` fires both; priority (LapCompleted drops pending corner).

### Out of scope

- Fuel/race-state coaching (slice 08).
- Modifying `Frame` dataclass fields.
- Modifying `compare_laps()` or `LapComparator` internals.
- Generating straight zones in the track model (data-authoring task; models without them will use inferred zones).
- Cross-process bus or WebSocket support.
- Refactoring `compare_laps()` to accept in-memory data (still uses temp Parquet bridge).
- Dynamic mode changes during a session (mode is set at startup and stays fixed).

## Design decisions

### CoachMode controls which detectors are active

`CoachMode.LAP` reproduces the slice 06 experience exactly — no `CornerExitDetector` is subscribed to the bus. This is the default so existing users see no change. `CoachMode.TURN` is for drivers who want real-time corner feedback but find the lap summary distracting. `CoachMode.ALL` gives the full experience.

### Top-N scales the LLM prompt, not just the output

When `--coach-top 1`, the LLM receives only the single worst loss fact and is prompted to produce a ≤ 20-word utterance. When `--coach-top 3`, it receives up to 3 and may use ≤ 35 words. This keeps the LLM response calibrated — giving it 3 items and asking for 20 words would produce a garbled summary.

### Partial-lap comparison

At corner exit, we only have frames from the start of the lap up to the current position. `compare_laps()` reads the full reference lap but the current lap Parquet only covers a portion. Losses/gains for corners that haven't been reached yet don't appear in the output. We filter to only the just-exited corner.

### Anti-chatter

Without a cooldown, the coach would speak after every corner that has a loss. The 8-second cooldown (in `session_time_s`) ensures at most one corner-exit call per 8 seconds. After-lap summaries are not subject to this cooldown.

### Speech window

Speaking mid-corner is unsafe. We only speak when:
1. The car is not inside a corner zone.
2. The next corner's entry is at least 50 m ahead (~1 second at 180 km/h).

If the track model defines `straight_zones`, those are used directly. If not, zones are inferred from gaps between corners.

### Priority and stale-drop

After-lap summaries (LapCompleted) take priority over corner-exit calls. If a LapCompleted utterance arrives while a corner-exit utterance is pending, the pending one is dropped via `SpeechQueue`'s stale-drop mechanism.

### Corner-exit vs after-lap

These two coaching channels coexist:
- **Corner-exit**: Short (≤ 20 words for `top=1`, ≤ 30 for `top=3`), fires mid-lap after significant loss, only in speech-safe zones.
- **After-lap**: Longer (≤ 20 words for `top=1`, ≤ 35 for `top=3`), fires at lap completion.

The after-lap summary uses the full lap's data and may surface different items than a mid-lap call. This is expected — the corner-exit call provides immediate feedback; the lap summary provides the big picture.

## CLI usage

```bash
# After-lap summary only, top 3 (default, same as slice 06):
python3 record_with_coach.py --out-dir sessions

# After-lap summary only, single biggest item:
python3 record_with_coach.py --out-dir sessions --coach-mode lap --coach-top 1

# Turn-by-turn only:
python3 record_with_coach.py --out-dir sessions --coach-mode turn

# Turn-by-turn only, single item per call:
python3 record_with_coach.py --out-dir sessions --coach-mode turn --coach-top 1

# Both, top 3 (full coaching):
python3 record_with_coach.py --out-dir sessions --coach-mode all

# Both, single item (minimal chatty coaching):
python3 record_with_coach.py --out-dir sessions --coach-mode all --coach-top 1

# With TTS engine selection (unchanged from slice 06):
python3 record_with_coach.py --out-dir sessions --coach-mode all --tts-engine kokoro
python3 record_with_coach.py --out-dir sessions --coach-mode turn --tts-engine file --tts-output /tmp/coach.txt
```

## Testing

### Unit tests (no sim needed)

1. **CoachMode / CoachConfig** — Default is `LAP` mode, `top=3`. CLI flags parse correctly.
2. **CornerExitDetector — emits on corner exit** — Feed frames that cross from inside a corner to outside; verify `CornerExited` fires with correct `corner_id` and distance.
3. **CornerExitDetector — no event mid-corner** — Feed frames all inside a corner; verify no event.
4. **CornerExitDetector — no event on first lap** — Before any `LapCompleted`, verify corner exits don't fire.
5. **CornerExitDetector — cooldown** — Exit two corners within 8 seconds; verify only the first fires.
6. **CornerExitDetector — reset on lap change** — Exit a corner in lap 2, then lap_number changes to 3; verify cooldown resets.
7. **LiveCornerFactGenerator — single corner** — With canned reference + model, generate facts for one corner exit; verify the utterance mentions the right corner.
8. **LiveCornerFactGenerator — below threshold** — Corner with loss_s < 0.1 → returns None.
9. **LiveCornerFactGenerator — no reference/model** — Unknown track → returns None.
10. **Top-N filtering in LiveFactGenerator** — `top=1` truncates to single worst loss; `top=3` includes up to 3.
11. **SpeechWindowChecker — straight zone** — In a defined straight zone → True.
12. **SpeechWindowChecker — in corner** — Inside a corner → False.
13. **SpeechWindowChecker — near next corner** — < 50 m before next corner → False.
14. **SpeechWindowChecker — inferred from corners** — Model with no straight_zones → infers from gaps.
15. **CoachTap — mode=lap only** — Only LapCompleted fires utterances; CornerExited events are ignored.
16. **CoachTap — mode=turn only** — Only CornerExited fires utterances; LapCompleted events produce no utterance.
17. **CoachTap — mode=all** — Both channels fire; LapCompleted takes priority over pending CornerExited.

### Integration tests (manual)

18. **End-to-end with recorder** — Run with each mode and verify behavior matches the CLI flags.

## Acceptance criteria

- `coach_config.py` extends `CoachConfig` with `CoachMode` enum and `top: int`.
- `corner_exit_detector.py` detects corner exits with cooldown.
- `CornerExited` event dataclass defined.
- `live_corner_fact_generator.py` generates per-corner utterances.
- `live_fact_generator.py` respects `CoachConfig.top` for top-N filtering.
- `speech_window.py` determines safe-speech zones.
- `corner_exit_prompt.py` provides short coaching prompt.
- `coach_tap.py` respects `CoachMode`: `lap` (no corner), `turn` (no lap), `all` (both).
- `live_coach.py` CLI has `--coach-mode` and `--coach-top` flags.
- After-lap summaries work in all modes (`lap` and `all`).
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
- Do not support dynamic mode changes during a session (set at startup only).

## Definition of Done

- [ ] `CoachMode` enum and `CoachConfig` with `mode` + `top` in `coach_config.py`
- [ ] `--coach-mode` and `--coach-top` CLI flags in `live_coach.py`
- [ ] `corner_exit_detector.py` detects corner exits with cooldown
- [ ] `CornerExited` event dataclass defined
- [ ] `live_corner_fact_generator.py` generates per-corner utterances
- [ ] `live_fact_generator.py` respects `CoachConfig.top` for top-N filtering
- [ ] `speech_window.py` determines safe-speech zones
- [ ] `corner_exit_prompt.py` provides short coaching prompt
- [ ] `coach_tap.py` respects CoachMode: lap-only, turn-only, or both
- [ ] After-lap summaries still work (slice 06 regression)
- [ ] Unit tests pass
- [ ] `npm run build` succeeds
- [ ] Feature test list updated in `package.json`
- [ ] `handoff.md` and `learnings.md` written