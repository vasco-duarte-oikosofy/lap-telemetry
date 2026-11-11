# Bug 35 — The debrief validator ignores drill-down facts, and provider errors crash the REPL

Two defects found by running a live session debrief against Ollama (2026-11).

## 1. Numbers from the corner drill-down are flagged as invented

Asking "why was Bretelle so bad?" showed `warning: numbers not in the facts:
1.559, 22.9, 70.4, 86.4` on stderr. All four numbers **are** in the facts — they
are in the corner block that was injected with the question (apex-speed spread
22.9 km/h, lap 4 at 86.4 km/h and +1.559 s). `validate_reply` was only given the
session grounding, not the drill-down it actually sent.

Effect: the validator cries wolf exactly where the coach is most specific, which
trains the reader to ignore it.

## 2. A provider error kills the conversation with a traceback

`coach_config.toml` points at `glm-5.1:cloud`, which Ollama retired:

```
openai.APIStatusError: Error code: 410 - glm-5.1 was retired on September 25, 2026.
Try glm-5.3-flash:cloud.
```

`--ask` catches `LLMAdapterError`, but `_call_via_openai` lets the SDK's own
exception type escape, so the REPL dies with a traceback after printing only the
command banner. A driver with a stale model or no network deserves one sentence,
not a stack trace.

## Fix

- `DebriefCoach.ask` validates against the grounding **plus** the drill-down it
  sent.
- `llm_adapter` wraps provider failures in `LLMAdapterError`.
- `Conversation._ask` catches `LLMAdapterError`, records it and keeps the session
  alive, telling the driver how to recover (`--no-llm`).
- `coach_config.toml` moves to a model the provider still serves.

## Status

✅ Fixed in the commit that files this.

## What the live runs added (2026-11)

Three runs against Ollama after the fix, with `glm-5.3-flash:cloud`:

- **Turns 1–2 were excellent** and every number traced to the facts (lap 11 with
  zero brake at corner 2, +0.129 s, 129.0 vs 136.3 km/h, brake peaks 0.34–0.80
  against 0.21, trail 11 m against 1 m). The grounding works.
- **Degeneration.** Earlier versions of the system prompt stated "at most 120
  words", and the cloud glm models literalised it into a word count
  (`Count: Positive(1) first(2): … You(57) arrive(58)`). The numeric word limit
  is gone from the prompt (it lives in the validator now), and a reply that
  annotates words is flagged as degenerate.
- **Provider-side truncation.** One reply arrived starting mid-word
  ("s not how slow you go —…"): the provider split the first characters into its
  `reasoning` field and returned the rest as content. Cannot be reconstructed
  safely, so the validator now warns when a reply does not end with a sentence
  terminator.

The deterministic `--no-llm` path is unaffected by all of this, and remains the
fallback when a model misbehaves.
