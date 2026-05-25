# Improvement: TTS-Friendly Utterance Formatting

## Problem

The current utterance output contains abbreviations and punctuation that text-to-speech
engines mispronounce or handle poorly:

- `km/h` → read as "k-m-slash-h" or skipped, not "kilometres per hour"
- `4m`, `9m` → read as "four-m" or "four-em", not "four metres"
- Em-dash `—` → causes unpredictable pause behaviour depending on the TTS engine
- Joined number+unit without space (`10m`) → tokenisation problems for some engines

Example of current output:
```
Turn 3 exit cost time — apex speed 10 km/h lower, released brakes 4m later,
back to throttle 9m later. Turn 5 good, on throttle 10m earlier.
```

Example of target output:
```
Turn 3 exit: apex speed ten kilometres per hour lower, released brakes
four metres later, back to throttle nine metres later.
Turn 5 good, back to throttle ten metres earlier.
```

## Change required

Update the system prompt in `prompt_templates.py` to add an explicit
**TTS output rules** section:

1. **No abbreviations.** Write out all units in full:
   - `km/h` → `kilometres per hour`
   - `m` (distance) → `metres`
   - `s` (seconds) → `seconds`
   - `kph` → `kilometres per hour`

2. **No em-dashes.** Replace `—` with a comma or a new sentence. The audio
   layer reads commas as a natural breath pause.

3. **Spell out small numbers as words** (one through ten). Larger numbers
   (e.g. 155) may stay as numerals — TTS handles those reliably.

4. **No slash characters.** Never write `km/h`, `m/s`, or similar.

5. **No parentheses or brackets.** TTS engines may read them aloud or skip
   the enclosed text entirely.

## Acceptance criteria

- Demo output contains no abbreviations (`km/h`, `m`, `s` as unit suffix).
- Demo output contains no em-dashes.
- Utterance still fits the ≤35 word constraint (units add words — the
  prompt may need to compensate by being more concise elsewhere).
- No other prompt rules (deduplication, fact-grounding, turn naming) regress.

## Scope

- Edit: `product/python/lap_telemetry/coach/prompt_templates.py` — add TTS
  rules to the system prompt.
- Verify: re-run `demo_coach_slice03.py --facts dev/fixtures/coach/barcelona_lap15_facts.json`
  and confirm the output reads naturally aloud.
- No changes needed to `llm_adapter.py`, `facts.py`, or the data layer.

## Out of scope

- SSML markup or phoneme hints (future, once a specific TTS engine is chosen).
- Number normalisation in code (let the LLM handle it via prompt).
- Word-count increase beyond 35 — tighten the prose instead.
