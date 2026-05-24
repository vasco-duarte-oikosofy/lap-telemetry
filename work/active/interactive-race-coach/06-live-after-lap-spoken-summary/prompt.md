# Slice 06: Live After-Lap Spoken Summary

## Goal

At the end of each completed lap, analyze the lap against the reference, generate one LLM utterance from the coaching facts, and speak it on the next straight. This is the first end-to-end coaching loop: recorder → live bus → lap detector → fact generator → LLM → TTS → speaker.

## User-visible result

A single command starts the recorder, coach, and speaker together:

```bash
python3 record_with_coach.py --out-dir sessions
```

After each completed lap, the driver hears a concise engineering call such as:

> "Lost three tenths mostly in turn 4 entry and turn 5 exit. Minimum speed was 7 km/h lower through turn 4."

The call is spoken via TTS after a brief delay (to find a speech window — see below). The recorder continues writing Parquet normally.

## Architecture risk validated

Can the full coaching loop run at live speed without disturbing the 50 Hz recorder? The answer must be yes: fact generation, LLM call, and TTS synthesis all happen off the recorder thread, and the speech queue drops stale utterances if the next lap starts before the current one finishes speaking.

## Pipeline

```
Recorder (50 Hz loop)
   │
   ├─→ SessionWriter (Parquet — unchanged)
   │
   └─→ QueuedBus (slice 05)
         │
         └─→ LapDetector (slice 05)
               │
               ├─ NewLap event
               └─ LapCompleted event (carries frozen frames)
                     │
                     └─→ FactGenerator
                           │ (analyzes completed lap vs reference)
                           │
                           └─→ LLM adapter
                                 │ (generates utterance from facts)
                                 │
                                 └─→ SpeechQueue
                                       │ (non-blocking, stale-drop)
                                       │
                                       └─→ TTS adapter → speaker
```

All steps after the bus publish happen on the QueuedBus worker thread or the SpeechQueue worker thread — never on the 50 Hz recorder thread.

## Scope

### In scope

1. **Reference-lap resolver** (`lap_telemetry/coach/reference_resolver.py`)
   - Maps a track name (from `Frame.track_name`) to a reference lap file.
   - Looks for `product/data/reference-laps/<track-slug>*_time_*.parquet`.
   - If multiple references exist for a track, picks the fastest (smallest `_time_` value).
   - Returns a `Path` or `None` if no reference exists for the track.
   - Caches the resolved path so disk scanning happens once per track.

2. **Track-model resolver** (`lap_telemetry/coach/track_model_resolver.py`)
   - Maps a track name to a track coaching model JSON file.
   - Looks for `product/data/track-coaching/<track-slug>*.json`.
   - If multiple models exist for a track (different vehicle suffixes), picks the first match.
   - Returns a `Path` or `None` if no model exists.
   - Caches the resolved path.

3. **Live fact generator** (`lap_telemetry/coach/live_fact_generator.py`)
   - Receives a `LapCompleted` event (from the `LapDetector`).
   - Resolves the reference lap and track model for the completed lap's track name.
   - If no reference or model is found, emits a warning to stderr and skips utterance generation.
   - Converts the `LapCompleted.frames` list into a temporary Parquet file (or in-memory structure) that `compare_laps()` can consume.
   - Calls `compare_laps()` to produce `LapComparisonFacts`.
   - Passes facts to `generate_utterance()` to produce a coaching text string.
   - Returns the utterance string (or `None` if any step fails).

4. **Coach orchestrator** (enhance `lap_telemetry/coach/coach_tap.py`)
   - Wires together: `QueuedBus` → `LapDetector` → `LiveFactGenerator` → LLM → `SpeechQueue`.
   - On `LapCompleted`: calls `LiveFactGenerator`, feeds utterance to `SpeechQueue`.
   - On `NewLap`: no action (utterance from the previous lap's completion is already queued).
   - Manages `SpeechQueue` lifecycle (shutdown on Ctrl+C).
   - Prints debug info to stderr: fact generation timing, utterance text, skip reasons.
   - If the LLM call fails or times out, logs the error and continues (no crash).

5. **Frame-to-Parquet conversion** (`lap_telemetry/coach/frames_to_parquet.py`)
   - Converts a `list[Frame]` to a temporary Parquet file that `compare_laps()` can read.
   - Reuses the `SessionWriter` schema for column names and types.
   - Writes to a temp file in the system temp directory, returns the `Path`.
   - Caller is responsible for cleaning up the temp file after `compare_laps()` completes.

6. **CLI entry point** (enhance `lap_telemetry/coach/live_coach.py`)
   - `--out-dir` — Parquet session output directory (passed to recorder).
   - `--tts-engine` — TTS engine override (`kokoro` | `pyttsx3` | `file`).
   - `--tts-output` — output file path when using `file` engine.
   - Creates a `QueuedBus`, wires a `CoachTap` with fact generation, LLM, and TTS.
   - Ctrl+C shuts down cleanly: stops bus, flushes speech queue, closes recorder writer.

7. **Launcher script** (enhance `record_with_coach.py`)
   - Updated to use the enhanced `live_coach.py` entry point with TTS.
   - Same UX: `python3 record_with_coach.py --out-dir sessions`.

8. **Unit tests** (`dev/scripts/test_live_after_lap_spoken_summary.py` + `.js` wrapper)
   - Reference resolver: finds reference lap for known track, returns None for unknown track.
   - Track model resolver: finds model for known track, returns None for unknown track.
   - Frames-to-Parquet: converts a list of fake frames to a valid temporary Parquet file with the right schema.
   - Live fact generator: with a canned reference + model, generates facts from fake frames.
   - Live fact generator: skips gracefully when no reference or model found.
   - Coach orchestrator: wires up bus → detector → fact gen → (mock LLM) → (mock TTS).

### Out of scope

- Corner-exit coaching (slice 07) — this slice only speaks after lap completion.
- Speech window detection (waiting for a straight to speak) — the SpeechQueue's stale-drop handles this for now. If the next lap starts before the utterance finishes, the queue drops the pending one.
- Fuel/race-state channels in `Frame` (slice 08+).
- Any modification to `Frame` dataclass fields.
- Any modification to `compare_laps()` or `LapDetector` beyond wiring.
- Post-session review or report generation.

## Design decisions

### Frame-to-Parquet conversion

`compare_laps()` reads Parquet files. The live pipeline has `Frame` objects in memory, not Parquet files. The simplest correct approach is to write the completed lap's frames to a temporary Parquet file, call `compare_laps()`, then clean up.

This is a temporary bridge. A future slice should refactor `compare_laps()` to accept in-memory data directly, but that is out of scope for this slice. The temp file approach:
- Is correct (shares the same code path as offline comparison).
- Is testable (same Parquet writer used by the recorder).
- Has minimal overhead (a few hundred rows written once per lap, ~50 KB).

### Speech timing

Slice 07 will add proper speech-window detection (waiting for a straight after corner exit before speaking). For this slice, the utterance is enqueued immediately on `LapCompleted`. The `SpeechQueue` handles:
- Non-blocking enqueue (the fact generator thread doesn't wait for TTS).
- Stale drop (if a new utterance arrives before the previous one finishes, the stale one is replaced).
- Clean shutdown.

This is good enough for practice sessions where the driver completes a lap and receives coaching on the next lap's start/finish straight.

### Error handling

Every step after bus publish can fail without crashing the recorder:
- No reference lap for this track → skip with warning, no utterance.
- No track model for this track → skip with warning, no utterance.
- `compare_laps()` raises → log error, skip utterance.
- LLM call fails or times out → log error, skip utterance.
- TTS fails → log error, continue recording.

The recorder's 50 Hz loop is never affected.

### Reference lap resolution

The track name from LMU (e.g. `Circuit de Barcelona-Catalunya`) is slugified to match reference lap filenames (e.g. `circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet`). Slugification follows the same logic as `SessionWriter._track_slug()`.

## Testing

### Unit tests (no sim needed)

1. **Reference resolver — known track** — Resolve `circuit-de-barcelona` → find the Barcelona reference lap file.
2. **Reference resolver — unknown track** — Resolve `unknown-track-xyz` → return `None`.
3. **Reference resolver — caching** — Resolve same track twice → second call uses cached path.
4. **Track model resolver — known track** — Resolve `circuit-de-barcelona` → find the Barcelona track coaching model.
5. **Track model resolver — unknown track** — Resolve `unknown-track-xyz` → return `None`.
6. **Frames to Parquet** — Create a list of fake Frames, convert to Parquet, verify the file has the expected columns and row count.
7. **Live fact generator — happy path** — With a known reference lap and track model, generate facts from fake frames. Verify `LapComparisonFacts` has track_id and at least one loss or gain.
8. **Live fact generator — no reference** — Track with no reference lap → skip with warning, return `None`.
9. **Live fact generator — no model** — Track with no coaching model → skip with warning, return `None`.

### Integration tests (manual)

10. **End-to-end with recorder** — Run `python3 record_with_coach.py --out-dir sessions` with LMU. Verify:
    - Recorder writes Parquet normally.
    - After each lap, an utterance is spoken.
    - If no reference exists for the track, a warning is printed and no utterance is spoken.
    - Ctrl+C shuts down cleanly.

## Acceptance criteria

- `reference_resolver.py` resolves track names to reference lap files.
- `track_model_resolver.py` resolves track names to coaching model files.
- `frames_to_parquet.py` converts `list[Frame]` to a valid temporary Parquet file.
- `live_fact_generator.py` generates facts from a `LapCompleted` event.
- `coach_tap.py` wires bus → detector → fact gen → LLM → TTS.
- `live_coach.py` CLI has `--tts-engine` and `--tts-output` flags.
- `record_with_coach.py` starts the full pipeline with one command.
- Unit tests pass (`bash scripts/test-summary.sh`).
- `npm run build` succeeds (no JS changes expected, but verify no regression).
- `handoff.md` and `learnings.md` created.
- Feature tests added to `package.json` under `interactive-race-coach`.

## Non-goals

- Do not add speech-window detection (slice 07).
- Do not add corner-exit coaching (slice 07).
- Do not modify `compare_laps()` or `LapDetector`.
- Do not modify `Frame` dataclass.
- Do not add fuel/race-state channels (slice 08+).
- Do not build cross-process bus or WebSocket support.

## Definition of Done

- [ ] `reference_resolver.py` resolves track names to reference lap paths
- [ ] `track_model_resolver.py` resolves track names to track model paths
- [ ] `frames_to_parquet.py` converts Frame list to temporary Parquet
- [ ] `live_fact_generator.py` generates facts + utterance from LapCompleted
- [ ] `coach_tap.py` wires LapCompleted → fact gen → LLM → SpeechQueue
- [ ] `live_coach.py` CLI has TTS engine flags
- [ ] `record_with_coach.py` starts full pipeline
- [ ] Unit tests pass
- [ ] Recorder produces identical Parquet with and without bus (verified in slice 05)
- [ ] Feature test list updated in `package.json`
- [ ] Full test suite passes
- [ ] Build succeeds
- [ ] `handoff.md` and `learnings.md` written