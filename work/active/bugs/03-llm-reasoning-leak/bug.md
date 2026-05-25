# Bug 03: LLM leaks chain-of-thought into spoken utterance

## Observed

```
lap-telemetry: [coach] utterance: - this seems like a hard rule. Let me include it:
```

## Root cause

`"Output ONLY the utterance text. No preamble, no labels, no quotes."` is the last line of the system prompt but isn't strong enough — the model sometimes ignores it when it has low confidence about the facts and starts reasoning out loud.

## Fix plan

1. Add a named Rule 10 to `SYSTEM_PROMPT_TEMPLATE`: explicit bad/good example + "If you have no useful fact to state, output an empty string".
2. Add `_is_meta_output(utterance)` filter in `live_fact_generator.py` that returns `True` for utterances starting with `"-"`, containing `"let me"`, `"i will"`, `"as a rule"`, `"this seems"`, or ending with `":"`. Return `None` instead of speaking garbage.

## Files

- `product/python/lap_telemetry/coach/prompt_templates.py`
- `product/python/lap_telemetry/coach/live_fact_generator.py`

## Test

`dev/scripts/test_llm_utterance_guard.py`

## Status

🔧 In progress
