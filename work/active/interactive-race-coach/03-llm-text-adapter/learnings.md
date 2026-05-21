# Slice 03 Learnings: LLM Text Adapter

## Surprises

1. **litellm model prefix format** — litellm requires the model name to be
   prefixed with the provider: `anthropic/claude-sonnet-4-20250514`, not just
   `claude-sonnet-4-20250514`. This differs from the Anthropic SDK which just
   needs the bare model name. Our config stores the bare model name; the
   adapter prepends the provider prefix for litellm.

2. **TOML parsing on Python 3.10** — `tomllib` was added in Python 3.11. Since
   we target 3.10+, we need a fallback parser. Writing a minimal parser for
   our flat `[llm]` table was straightforward: handle strings, ints, floats,
   comments, and a single section header. No need for the full TOML spec.

3. **Constraints exclusion from user message** — The `constraints` dict in
   `LapComparisonFacts` is already encoded in the system prompt template
   (max_words, style). Sending it again in the user message JSON would
   confuse the LLM and waste tokens. The prompt builder strips it out.

4. **Same-corner deduplication is a prompt-layer concern, not a data-layer one** —
   The data layer deliberately produces multiple entries for the same corner
   (exit_brake, minimum_speed, exit_throttle are all different measurements).
   Merging them at the data layer would lose information. The LLM prompt
   contract instructs the model to combine same-corner phases into one
   coaching point. This separation is clean and testable.

## Context for the next agent

### File locations

- LLM adapter: `product/python/lap_telemetry/coach/llm_adapter.py`
- Config loader: `product/python/lap_telemetry/coach/coach_config.py`
- Prompt templates: `product/python/lap_telemetry/coach/prompt_templates.py`
- CLI: `product/python/lap_telemetry/coach/generate_utterance.py`
- Demo: `product/python/demo_coach_slice03.py`
- Config file: `coach_config.toml` (project root)
- Canned fixture: `dev/fixtures/coach/barcelona_lap15_facts.json`

### Design decisions

1. **litellm-first, openai SDK fallback** — litellm provides a unified
   `completion()` call across all major providers. If not installed, we fall
   back to the openai SDK with a custom `base_url` (most providers support
   the OpenAI chat format). This avoids writing per-provider adapter code.

2. **Config in project root** — `coach_config.toml` lives in the project root
   for simplicity. The `COACH_CONFIG` env var can override the path. On
   Windows, this means next to the repo checkout.

3. **No API keys in config files** — The config stores only the *name* of the
   environment variable (e.g. `ANTHROPIC_API_KEY`). The actual key is read
   from the environment at runtime. This is a deliberate security choice.

4. **Prompt contract is versioned in code** — The system prompt template is
   a Python constant. If we need A/B testing or version management later, we
   can add a `prompt_version` field to `LapComparisonFacts.constraints`.

5. **`generate_utterance` CLI module** — Uses `python -m lap_telemetry.coach.generate_utterance`
   rather than a subcommand on the main `lap_telemetry` CLI. This keeps the
   coach-specific deps (litellm/openai) separate from the recorder CLI.

### Manual smoke test with real LLM

To test with an actual LLM API (requires an API key):

```bash
# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run with canned facts
python3 -m lap_telemetry.coach.generate_utterance \
  --facts dev/fixtures/coach/barcelona_lap15_facts.json \
  --debug

# Run the demo script
cd product/python
python3 demo_coach_slice03.py --facts ../../dev/fixtures/coach/barcelona_lap15_facts.json
```

Expected output: one concise utterance ≤35 words mentioning turn 3 loss,
something like: "Lost four tenths in turn 3 — minimum speed 10 km/h lower,
released brakes 4 m later. Protect exit speed there."

This is a smoke test, not CI. LLM output varies between calls.

## Gotchas to avoid

1. **litellm model prefix** — Don't forget the `provider/` prefix when calling
   litellm. Our adapter handles this automatically (`f"{config.provider}/{config.model}"`).

2. **TOML on Python 3.10** — `tomllib` doesn't exist on 3.10. Our fallback
   parser handles the flat `[llm]` table but NOT nested tables, arrays, or
   multiline strings. If the config format grows, we may need to add `tomli`
   as a dependency or switch to a different config format.

3. **Windows env var case sensitivity** — On Windows, env var names are
   case-insensitive. `ANTHROPIC_API_KEY` and `Anthropic_Api_Key` are the same.
   Our code uses `os.environ.get()` which respects this on Windows.

4. **Constraints excluded from user message** — If you add facts manually and
   forget that `constraints` is stripped, you might wonder why the LLM
   ignores max_words. It's in the system prompt, not the facts JSON.