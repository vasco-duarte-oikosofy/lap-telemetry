# Slice 03 Handoff: LLM Text Adapter

## Status

✅ Complete (including Ollama/glm-5.1:cloud validation)

## What's on disk now

### Product code (Python)

- `product/python/lap_telemetry/coach/prompt_templates.py` — System prompt template
  - `build_messages(facts)` → list of system + user message dicts
  - System prompt enforces: ≤35 words, fact-only, same-corner deduplication,
    distance delta → natural language, actionable language
  - User message excludes `constraints` (already in system prompt)

- `product/python/lap_telemetry/coach/coach_config.py` — Configuration loader
  - `LLMConfig` dataclass with provider/model/temperature/max_tokens/base_url
  - `api_key` property reads from the named env var (not from file)
  - `load_config(path)` reads TOML, applies env var overrides
  - Fallback TOML parser for Python 3.10 (no `tomllib`)

- `product/python/lap_telemetry/coach/llm_adapter.py` — LLM adapter
  - `generate_utterance(facts, config)` → utterance string
  - Uses litellm first, falls back to openai SDK
  - Logs full input/output for debugging
  - Raises `LLMAdapterError` on missing API key or empty response

- `product/python/lap_telemetry/coach/generate_utterance.py` — CLI entry point
  - `--facts <json>` loads canned facts and sends to LLM
  - `--lap` generates facts from parquet files first
  - `--debug` prints full facts JSON to stderr
  - Prints utterance to stdout

- `product/python/demo_coach_slice03.py` — End-to-end demo script
  - Defaults to Barcelona fixtures
  - `--facts` for canned JSON input
  - Prints facts JSON then utterance

### Configuration

- `coach_config.toml` (project root) — Default config with Anthropic provider
  - No API keys in file; only env var names
  - Env var overrides: `COACH_LLM_PROVIDER`, `COACH_LLM_MODEL`, `COACH_CONFIG`

### Data artifacts

- `dev/fixtures/coach/barcelona_lap15_facts.json` — Canned facts from Barcelona
  lap 15 comparison (3 losses in turn 3 + 2 gains in turn 5)

### Test scripts

- `dev/scripts/test_llm_text_adapter.js` — 17 assertions covering:
  - Prompt template rendering (word limit, same-corner dedup, distance deltas)
  - Config loading (defaults, TOML, env var overrides, COACH_CONFIG path)
  - API key resolution (from env var, not config file)
  - Facts loading and roundtrip
  - LLM adapter error on missing API key

## Commands to run

### CLI usage (with canned facts)

```bash
python3 -m lap_telemetry.coach.generate_utterance \
  --facts dev/fixtures/coach/barcelona_lap15_facts.json \
  --track-config product/data/track-coaching/circuit-de-barcelona_dkr-engineering-4-elms25.json
```

### CLI usage (with live fact generation)

```bash
python3 -m lap_telemetry.coach.generate_utterance \
  --lap \
  --current-lap dev/fixtures/coach/barcelona_lap15_current.parquet \
  --reference-lap product/data/reference-laps/circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet \
  --track-config product/data/track-coaching/circuit-de-barcelona_dkr-engineering-4-elms25.json
```

### Manual smoke test (requires API key)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
cd product/python
python3 demo_coach_slice03.py
```

### Run tests

```bash
bash scripts/test-summary.sh --feature llm-text-adapter   # feature-specific (7 scripts)
bash scripts/test-summary.sh                               # full suite (50 scripts)
```

## Feature flags

None for this slice.

## New helpers worth knowing about

### `build_messages(facts: LapComparisonFacts) -> list[dict]`

Returns the system prompt + user message pair for the LLM. System prompt
embeds the word limit and all coaching rules. User message contains only the
factual data (constraints excluded).

### `load_config(path=None) -> LLMConfig`

Resolves config path from: argument → `COACH_CONFIG` env → `coach_config.toml`
in CWD. Reads TOML `[llm]` section, applies `COACH_LLM_PROVIDER` and
`COACH_LLM_MODEL` env overrides.

### `generate_utterance(facts, config=None) -> str`

One function to call. If config is None, loads from default path. Logs
full input/output pair at DEBUG level.

### `_load_facts_from_json(path) -> LapComparisonFacts`

Loads a canned facts JSON file back into the dataclass. Used by CLI and demo.

## Deferred TODOs

1. **Streaming/chunking** — Unnecessary for ≤35 words; deferred.
2. **Prompt A/B testing** — Need a `prompt_version` field and variant loader.
3. **OpenAI SDK fallback base URL** — Only DeepSeek and Google have explicit
   base URLs. Other providers use SDK defaults. May need more mappings.
4. **Reasoning model support** — glm-5.1:cloud (and similar reasoning
   models like deepseek-r1) put chain-of-thought in `reasoning` field and
   may return empty `content`. The adapter now:
   - Detects empty content with reasoning present
   - Extracts the last quoted utterance from reasoning as fallback
   - Falls back to the last meaningful sentence if no quotes found
   - Logs a warning suggesting to increase max_tokens
5. **max_tokens bumped** — Default is now 4096 to accommodate reasoning
   models that need substantial thinking budget before producing content.
   The actual utterance is still ≤35 words — this just lets the model
   think without hitting the ceiling.
6. **Ollama support** — `ollama` is a first-class provider routed through
   the OpenAI-compatible SDK with `base_url = http://localhost:11434/v1`.
   Local Ollama doesn't validate API keys but the openai SDK requires
   *something* — set `OLLAMA_API_KEY=local` as a dummy value.
7. **TOML parser upgrade** — The fallback parser only handles flat [llm]
   tables. If config grows, add `tomli` as a dependency for Python 3.10.

## Test results

- `bash scripts/test-summary.sh --feature llm-text-adapter`: ✅ 181 assertions / 7 scripts
- `bash scripts/test-summary.sh`: ✅ 1224 assertions / 50 scripts
- `npm run build`: ✅