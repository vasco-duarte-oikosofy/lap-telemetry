# Bug 09: Utterances are hard to parse when spoken aloud during a lap

## Observed

Current utterance from the LLM (using bug 04's swapped fixture):

> "Turn 3, carried more speed through apex, back to throttle four metres earlier. Turn 5, released brakes ten metres later on exit. Turn 1, braked twelve metres later."

Problems when hearing this during a lap:

1. **No gain/loss framing.** The listener does not know whether each point is good or bad until they've parsed the whole sentence. Spoken language needs the verdict first: "You gained time in turn 3" or "You lost time in turn 5."
2. **Gains and losses blurred together.** Gains and losses alternate in a single stream with no audible separator. In the car, the driver needs a clear break between "here's what you did well" and "here's where you lost time."
3. **No subject-verb structure.** "Turn 3, carried more speed" drops the subject. A race engineer on the radio says "You lost time in turn 5" not "Turn 5, released brakes ten metres later on exit."

## Desired improvement

Rough examples of what sounds better (not prescriptive — the prompt should produce these patterns, not these exact words):

- **Before:** "Turn 3, carried more speed through apex, back to throttle four metres earlier."
- **After:** "You gained time in turn 3 by carrying more speed through the apex, and back on throttle four metres earlier."

- **Before:** "Turn 5, released brakes ten metres later on exit. Turn 1, braked twelve metres later."
- **After:** "You lost time at turn 5, and at turn 1. At turn 5 you released the brakes ten metres later on exit. At turn 1 you braked twelve metres later."

Key structural changes:
1. **Lead with gain or loss.** Every coaching point starts with "You gained time" or "You lost time" so the driver knows the verdict instantly.
2. **Separate gains from losses.** Gains first, then a short pause, then losses. Not interleaved.
3. **Natural subject-verb order.** "You lost time at turn 5" not "Turn 5, released brakes later."

## Fix plan

This requires a prompt change plus a test corpus that exercises different utterance patterns (gain-only, loss-only, mixed, contradictory). The test corpus will let us iterate on the prompt quickly without needing a live lap.

### Slice 1: Create a test corpus

Create multiple fact JSON fixtures that cover the utterance patterns described above:
- `barcelona_mixed_gains_and_losses_facts.json` — gains and losses in the same lap (current `barcelona_swapped_faster_driver_facts.json` is one example, but mixed-gain-loss should have both clearly)
- `barcelona_gains_only_facts.json` — only gains, no losses
- `barcelona_losses_only_facts.json` — only losses, no gains
- `barcelona_single_corner_facts.json` — one corner only, minimal data

Each fixture should have `expected_patterns` — a list of strings that a good utterance should contain (e.g. "you gained", "you lost") and a list of `forbidden_patterns` — strings that a bad utterance should NOT contain (e.g. interleaved gain-then-loss without a break).

### Slice 2: Add prompt rules for utterance structure

Add/modify rules in `SYSTEM_PROMPT_TEMPLATE`:

1. **Structure rule:** "Lead every coaching point with 'You gained time' or 'You lost time' for the relevant corner."
2. **Separation rule:** "Group gains together first, then losses. Separate the two groups with a sentence break."
3. **Subject rule:** "Use 'you' as the subject, not imperative or passive constructions."

### Slice 3: Add a test that builds messages from the corpus and checks prompt content

Like `test_contradictory_speed_coaching.py` — check that the prompt template contains the new rules.

## Files

- `product/python/lap_telemetry/coach/prompt_templates.py` — prompt rules
- `dev/fixtures/coach/` — test corpus fixtures
- `dev/scripts/test_utterance_readability.py` — test script

## Status

✅ Fixed in commit `addb36a`

- Prompt rules 11 (gain/loss framing), 12 (gain-first ordering), and 13 (speed vs time-loss interpretation) added to `SYSTEM_PROMPT_TEMPLATE`
- 5 test corpus fixtures created in `dev/fixtures/coach/`
- Test script `dev/scripts/test_utterance_readability.py` passes

Moved to `work/completed/bugs/`.