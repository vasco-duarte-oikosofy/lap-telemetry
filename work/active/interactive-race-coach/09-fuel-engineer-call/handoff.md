# Slice 09 — Fuel Engineer Call — Handoff

## What was delivered

- **`fuel_prompt.py`** — `build_fuel_messages(facts: FuelFacts)` builds a
  2-message list (system + user) for the LLM. System prompt encodes the race
  engineer persona, ≤ 20-word limit, TTS rules, and status-specific guidance.

- **`live_fuel_fact_generator.py`** — `LiveFuelFactGenerator` wraps
  `compute_fuel_facts()` and gates the LLM call behind three conditions:
  session_type == "race", and either WARNING/CRITICAL status or a ≤ 3-lap
  margin between laps_of_fuel_remaining and race_laps_remaining.

- **`coach_config.py`** — `CoachRunConfig` gains `fuel_calls: bool = False`.

- **`coach_tap.py`** — accepts optional `fuel_fact_generator` parameter; calls
  `generate(event.frames)` after the lap-summary utterance when
  `config.fuel_calls` is True.

- **`live_coach.py`** — `--fuel-calls` flag (store_true); wires
  `fuel_utterance_fn` → `LiveFuelFactGenerator` → `CoachTap`.

- **`test_fuel_engineer_call.py`** + **`.js`** — 19 Python assertions covering
  all 14 spec items. JS wrapper follows the `test_corner_exit_coaching.js`
  pattern.

- **`package.json`** — `test_fuel_engineer_call.js` added to
  `testFeatures["interactive-race-coach"]`.

## State

All 19 Python assertions pass. The JS wrapper (like all Python-backed JS
wrappers on Windows) relies on `python3`; the harness reports failures there
because the machine only has `python`. This is a pre-existing environment
constraint, not a regression — `test_corner_exit_coaching.js` and others
fail the same way.

## How to test

```powershell
$env:PYTHONPATH = "product/python"
$env:PYTHONIOENCODING = "utf-8"
python dev/scripts/test_fuel_engineer_call.py
```

## Next slice suggestions

- Slice 10: pit-window logic (earliest vs latest lap to pit based on fuel
  model + race laps remaining).
- Or: wire `--fuel-calls` into an end-to-end smoke test with a saved
  race Parquet to validate the real LLM utterance quality.
