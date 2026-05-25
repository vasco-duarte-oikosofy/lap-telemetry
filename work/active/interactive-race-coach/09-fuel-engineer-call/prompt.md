# Slice 09: Fuel Engineer Call

## Context

You are working inside `C:\Users\duart\lap-telemetry`, a telemetry recorder and
lap-comparison tool for Le Mans Ultimate (LMU). The codebase lives under
`product/python/lap_telemetry/`. All Python source is under
`product/python/lap_telemetry/`; test scripts live in `dev/scripts/`.

This is slice 09 of the interactive-race-coach mission. Slices 01–08 are
complete. The relevant prior work:

- **Slice 08** added `Frame.fuel_l`, `Frame.fuel_capacity_l`,
  `Frame.session_type`, `Frame.session_time_remaining_s`,
  `Frame.race_laps_total` — all nullable, populated from LMU shared memory.
  It also delivered `FuelFacts` dataclass and `compute_fuel_facts()` in
  `product/python/lap_telemetry/coach/fuel_facts.py`. That module is the
  data source for this slice.

- **Slices 06–07** delivered the live coaching pipeline:
  `CoachTap` (`coach_tap.py`) orchestrates bus → `LapDetector` →
  `LiveFactGenerator` → `SpeechQueue` → TTS. `CoachTap._on_lap_completed`
  fires after each lap and is the natural hook for the fuel call.

- The LLM interface is `generate_utterance(facts, config)` from
  `llm_adapter.py`, and the low-level `_call_llm(config, messages)`.
  Messages follow the `[{role, content}, …]` pattern used throughout
  `prompt_templates.py` and `corner_exit_prompt.py`.

- `CoachRunConfig` (`coach_config.py`) currently has `mode: CoachMode` and
  `top: int`. The live CLI entry point is `live_coach.py`.

- **TTS style rules** (from `prompt_templates.py`, rule 9) apply here too:
  full unit names, no abbreviations, spell one-through-ten as words,
  commas not em-dashes, no brackets.

---

## Goal

After each completed lap in a **race session**, speak one short fuel update
using deterministic facts from `compute_fuel_facts()` phrased by the LLM.
The call should feel like a real race engineer: calm, factual, only
actionable when the situation warrants it.

**Spoken only when session_type is "race".** Silent in practice/qualifying.
**Spoken only when fuel_status is WARNING or CRITICAL**, or when
`laps_of_fuel_remaining` and `race_laps_remaining` are both known and their
difference is ≤ 3 (cutting it close). Skip silently otherwise to avoid
cluttering low-stakes laps.

**Off by default.** Enabled with a new `--fuel-calls` CLI flag. The
`CoachRunConfig` gains `fuel_calls: bool = False`.

---

## Scope

### New files

1. **`product/python/lap_telemetry/coach/fuel_prompt.py`**

   Prompt template and builder for the fuel engineer call.

   ```python
   def build_fuel_messages(facts: FuelFacts) -> list[dict[str, str]]:
       """Build LLM messages for a fuel engineer utterance."""
   ```

   The system prompt encodes:
   - Race engineer persona, calm tone
   - ≤ 20 words
   - TTS rules (full units, spell 1–10, commas not dashes, no abbreviations)
   - Only state the facts supplied — never invent values
   - If CRITICAL: say fuel is low and driver must pit
   - If WARNING: say how many laps of fuel remain vs how many to go
   - If close (≤ 3 lap gap): brief note on the margin
   - Output ONLY the utterance, no preamble

   Example utterances (for reference, not literal):
   - "Fuel warning. Three laps of fuel, five to go. Consider pitting next lap."
   - "Fuel critical. One lap of fuel remaining. Pit this lap."
   - "Fuel okay, margin is two laps."

2. **`product/python/lap_telemetry/coach/live_fuel_fact_generator.py`**

   ```python
   class LiveFuelFactGenerator:
       """Compute FuelFacts from live frames and generate a spoken fuel update."""

       def __init__(self, utterance_fn: Callable[[FuelFacts], str | None]) -> None: ...

       def generate(self, frames: list[Frame]) -> str | None:
           """Return a spoken utterance or None if no call is warranted."""
   ```

   Logic:
   - Calls `compute_fuel_facts(frames)` on the accumulated lap frames
   - Returns `None` if `session_type != "race"` or conditions not met (see above)
   - Calls `utterance_fn(facts)` (the LLM closure) to generate the utterance
   - Returns the utterance string, or `None` on LLM error

3. **`dev/scripts/test_fuel_engineer_call.py`** + **`dev/scripts/test_fuel_engineer_call.js`**

   The `.js` wrapper follows the exact same pattern as
   `test_corner_exit_coaching.js` — a Node child-process wrapper that runs
   the Python test and forwards stdout/stderr.

   Unit tests (no sim, no LLM — use a mock `utterance_fn`):
   1. `build_fuel_messages()` returns two messages (system + user)
   2. System message contains the word "race engineer"
   3. User message contains `laps_of_fuel_remaining` value from facts
   4. `LiveFuelFactGenerator.generate()` returns `None` for session_type "practice"
   5. Returns `None` for session_type "qualifying"
   6. Returns `None` when fuel_status is "OK" and no close-margin condition
   7. Returns a string when fuel_status is "WARNING" (mock utterance_fn returns "test utterance")
   8. Returns a string when fuel_status is "CRITICAL"
   9. Returns a string when laps_of_fuel_remaining and race_laps_remaining differ by ≤ 3
   10. Returns `None` when utterance_fn returns `None` (LLM error path)
   11. Returns `None` when frames list is empty
   12. Returns `None` when all fuel data is None (UNKNOWN status)
   13. Mock utterance_fn is called with a `FuelFacts` object (not raw frames)
   14. Does not call utterance_fn when condition check returns False (no wasted LLM calls)

### Modified files

4. **`product/python/lap_telemetry/coach/coach_config.py`**

   Add `fuel_calls: bool = False` to `CoachRunConfig`:
   ```python
   @dataclass
   class CoachRunConfig:
       mode: CoachMode = CoachMode.LAP
       top: int = 3
       fuel_calls: bool = False
   ```

5. **`product/python/lap_telemetry/coach/coach_tap.py`**

   - Add optional `fuel_fact_generator: LiveFuelFactGenerator | None = None`
     parameter to `CoachTap.__init__`.
   - In `_on_lap_completed`, after the existing lap-summary utterance path
     (if `config.fuel_calls` is True and `fuel_fact_generator` is not None):
     call `fuel_fact_generator.generate(event.frames)` and enqueue the result
     if non-None. Fuel call goes on the queue after the lap summary.
   - `LapCompleted.frames` — check whether the event already carries the frame
     list. If not, use `self._detector.current_lap_frames` (the frames for the
     just-completed lap, accessible at the time `_on_lap_completed` fires).
     Look at `lap_detector.py` to see what `LapCompleted` carries.

6. **`product/python/lap_telemetry/coach/live_coach.py`**

   - Add `--fuel-calls` flag (store_true, default False).
   - Pass `fuel_calls=args.fuel_calls` to `CoachRunConfig`.
   - Create a `fuel_utterance_fn` closure (same pattern as `utterance_fn` and
     `corner_utterance_fn`) that calls `_call_llm(config, build_fuel_messages(facts))`.
   - Create `LiveFuelFactGenerator(utterance_fn=fuel_utterance_fn)`.
   - Pass it to `CoachTap` as `fuel_fact_generator=...`.

7. **`package.json`**

   Add `"test_fuel_engineer_call.js"` to the `interactive-race-coach` feature
   tests array. Follow the existing pattern in the `scripts.test` field.

---

## Key files to read before starting

- `product/python/lap_telemetry/coach/fuel_facts.py` — `FuelFacts`, `compute_fuel_facts()`
- `product/python/lap_telemetry/coach/prompt_templates.py` — message builder pattern and TTS rules
- `product/python/lap_telemetry/coach/corner_exit_prompt.py` — another message builder example
- `product/python/lap_telemetry/coach/coach_tap.py` — `_on_lap_completed` hook
- `product/python/lap_telemetry/coach/lap_detector.py` — `LapCompleted` event fields
- `product/python/lap_telemetry/coach/live_coach.py` — how new generators are wired
- `product/python/lap_telemetry/coach/live_corner_fact_generator.py` — generator pattern to follow
- `product/python/lap_telemetry/coach/coach_config.py` — `CoachRunConfig`
- `dev/scripts/test_corner_exit_coaching.js` — JS wrapper pattern
- `dev/scripts/test_corner_exit_coaching.py` — Python test pattern (mock utterance_fn)

---

## Acceptance criteria

- [ ] `build_fuel_messages(facts)` returns a valid 2-message list
- [ ] `LiveFuelFactGenerator.generate(frames)` returns `None` for non-race sessions
- [ ] `LiveFuelFactGenerator.generate(frames)` returns `None` when fuel_status is OK and margin > 3 laps
- [ ] `LiveFuelFactGenerator.generate(frames)` returns an utterance string for WARNING/CRITICAL
- [ ] `LiveFuelFactGenerator.generate(frames)` calls utterance_fn exactly once when condition met
- [ ] `CoachRunConfig` has `fuel_calls: bool = False`
- [ ] `CoachTap` accepts optional `fuel_fact_generator` parameter
- [ ] `live_coach.py` has `--fuel-calls` flag
- [ ] Unit tests pass: `bash scripts/test-summary.sh --feature interactive-race-coach`
- [ ] `npm run build` succeeds (no JS changes beyond package.json)
- [ ] `handoff.md` and `learnings.md` written

## Definition of Done

- [ ] `fuel_prompt.py` with `build_fuel_messages()`
- [ ] `live_fuel_fact_generator.py` with `LiveFuelFactGenerator`
- [ ] `coach_config.py` updated with `fuel_calls: bool = False`
- [ ] `coach_tap.py` updated to wire fuel generator
- [ ] `live_coach.py` updated with `--fuel-calls` flag
- [ ] `test_fuel_engineer_call.py` + `.js` with ≥ 14 assertions
- [ ] `package.json` updated
- [ ] All tests green
- [ ] `handoff.md` + `learnings.md` written in this folder

## Non-goals

- No tire data, weather, pit-window logic, or gap-to-next-pit
- No `CoachMode` changes — fuel calls are an independent `bool` flag, not a mode
- No new Parquet columns (slice 08 already added them)
- No per-lap fuel model refinement (average is fine)
- No fuel calls during practice or qualifying (silent by design)
