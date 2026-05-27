# Bug 09 handoff

## What's on disk

- `product/python/lap_telemetry/coach/prompt_templates.py` — added Rules 11 (GAIN/LOSS FRAMING), 12 (GAIN-FIRST ORDERING), renumbered old Rule 11 → Rule 13, updated Rule 5 examples and Rule 10 "Good" example to use "You gained"/"You lost" pattern
- `dev/fixtures/coach/barcelona_gains_only_facts.json` — test corpus: gains only, no losses
- `dev/fixtures/coach/barcelona_losses_only_facts.json` — test corpus: losses only, no gains
- `dev/fixtures/coach/barcelona_mixed_gains_and_losses_facts.json` — test corpus: both gains (T3) and losses (T10, T5)
- `dev/fixtures/coach/barcelona_single_corner_facts.json` — test corpus: one loss, minimal data
- `dev/scripts/test_utterance_readability.py` — 35-assertion test checking corpus fixtures, build_messages, and prompt rules
- `dev/scripts/test_utterance_readability.js` — JS wrapper for the Python test
- `package.json` — added `utterance-readability` feature test suite + added test to `interactive-race-coach` suite

## Prompt changes

Three new/updated rules in `SYSTEM_PROMPT_TEMPLATE`:

1. **Rule 5 examples** updated: "Lost two tenths" → "You lost two tenths", "Gained a tenth" → "You gained a tenth"
2. **Rule 10 "Good" example** updated: "Turn three exit, lost two seconds. Brake ten metres later." → "You lost time in turn 3 exit. Released brakes four metres later."
3. **Rule 11 (GAIN/LOSS FRAMING)**: Every coaching point must start with "You gained time" or "You lost time" — driver hears the verdict instantly
4. **Rule 12 (GAIN-FIRST ORDERING)**: Group gains first, then losses. Never interleave. Example given.
5. **Rule 13**: Former Rule 11 (SPEED vs TIME-LOSS INTERPRETATION) — content unchanged, just renumbered

## Feature test suites

- `utterance-readability`: 5 scripts, 130 assertions, ALL PASS
- `interactive-race-coach`: 18 scripts, 615 assertions, ALL PASS

## E2E results (all 5 corpus fixtures)

| Fixture | Utterance |
|---|---|
| gains_only | "You gained time in turn 3. Carried more speed through the apex, back on full throttle four metres earlier. You gained time at turn 1. Lifted twelve metres later." |
| losses_only | "You lost time at turn 5. Carried three kilometres per hour less through the apex, released brakes ten metres later. You lost time at turn 8. Released brakes eight metres later." |
| mixed | "You gained time in turn 3. Carried more speed, back on throttle four metres earlier. You lost time at turn 10. Apex nine metres late, nine point five kilometres per hour slower. You lost time at turn 5. Released brakes ten metres later." |
| single_corner | "You lost time at turn 3. Carried six kilometres per hour less through the apex, apexed eight metres later." |
| swapped (contradictory) | "You gained time in turn 3, carried more speed through apex, back on throttle four metres earlier. You lost time at turn 5, released brakes ten metres later." |

Every utterance now leads with "You gained time" or "You lost time", and gains are always reported before losses.

## Deferred

- `max_words` is still 35 for most fixtures; the mixed fixture uses 45 to allow enough room for the gain/loss separation. May need to tune `max_words` in production.
- No commit yet — awaiting final review before committing.