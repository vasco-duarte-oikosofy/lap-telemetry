# Mission 03: LLM Text Adapter

## Goal

Build an LLM adapter that takes structured coaching facts and a prompt
contract, sends them to a configured cloud model, and returns one concise
coaching utterance. Validates that provider configuration and prompt contract
work without live telemetry.

## Feature test command

```bash
bash scripts/test-summary.sh --feature llm-text-adapter
```

## Slices

### 03 — LLM Text Adapter with Canned Facts (this slice)

See `prompt.md` for full specification.

Key deliverables:
- `llm_adapter.py` — calls cloud LLM with facts + prompt
- `coach_config.toml` — provider/model/key config (no keys in files)
- `prompt_templates.py` — system prompt with deduplication rules
- `generate_utterance` CLI — canned facts → utterance
- Barcelona canned facts fixture

## Open items (carried from mission 01c)

- **Same-corner deduplication** — resolved in this slice's prompt contract
- **Multi-apex/chicanes** — documented in spec, needs Imola fixture
- **gain_end_distance_m naming** — low priority rename deferred