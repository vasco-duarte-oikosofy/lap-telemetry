# Handoff — Slice 07: LLM debrief summary

## State on disk

| File | Job |
|---|---|
| `product/python/lap_telemetry/session_brief.py` | `build_grounding` (≤4096 B), `corner_block` (≤1500 B), `find_corner` |
| `product/python/lap_telemetry/coach/debrief_coach.py` | `SYSTEM_PROMPT`, `build_messages`, `DebriefCoach`, `validate_reply`, template adapter |
| `product/python/lap_telemetry/coach/llm_adapter.py` | `call_llm` is now public (refactor `1fec045`) |
| `product/python/lap_telemetry/debrief.py` / `cli.py` | `--ask`, `--no-llm` |

## Usage

```bash
lap-telemetry debrief <session> --ask "where am I losing time?" --no-llm
lap-telemetry debrief <session> --ask "why was Bretelle slow?"        # needs config + key
```

Answers print on stdout; validator warnings go to stderr as `warning: …`.

## API

```python
coach = DebriefCoach(model=callable)      # tests / custom client
coach = DebriefCoach(config=LLMConfig)    # real provider via call_llm
coach = DebriefCoach()                    # deterministic template
answer = coach.ask(question, facts)       # CoachAnswer(text, warnings, messages)
```

`find_corner` matches "Bretelle", "t1", "corner 2", "turn 12" (case-insensitive);
numeric corner names need the "corner"/"turn" prefix to avoid false matches.

## Contract enforced by tests

System prompt: one positive with a number, single biggest recurring loss, ≤3
points, ≤120 words, exactly one question, never invent a number. Validation flags
numbers not in the grounding (with rounding tolerance), ≠1 question, >160 words.

## Budgets

Paul Ricard: grounding 2.8 KB, largest corner block 1.25 KB. COTA: 2.3 KB / 1.1
KB. The lap table caps at 26 rows and the block clips with "… (truncated)".

## Next

Slice 08 turns this into a REPL: history, `/corner`, `/laps`, `/plan`, `/save`,
and the two artifacts (`_debrief.json` with the transcript, `_plan.md` with the
targets). Reuse `DebriefCoach.ask` per turn and keep appending `messages` —
`CoachAnswer.messages` is already returned for exactly that.
