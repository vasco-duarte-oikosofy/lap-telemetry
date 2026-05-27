# Slice 11 Handoff: Low-Latency Utterance Generation

## What's on disk now

### New files

- **`product/python/lap_telemetry/coach/template_adapter.py`** — Deterministic template adapter with:
  - `TemplateAdapter.generate(facts)` — LapComparisonFacts → coaching phrase
  - `TemplateAdapter.generate_fuel_phrase(facts)` — FuelFacts → fuel phrase
  - `format_time(loss_s)` — Natural spoken English for TTS (a tenth, two tenths, etc.)
  - `_spell_number(n)` — Spell out 1–10, keep digits for 11+
  - Same-corner dedup: dominant phase leads, supporting phases become detail clauses with ", and"
  - Gain-first ordering: all gains before all losses
  - TTS output rules: full units, numbers 1–10 spelled out, no abbreviations/
  - Word-limit truncation: drops weakest sentences first
  - Exit phase with exit_distance_delta_m: interprets as throttle timing (same as exit_throttle)

- **`product/python/lap_telemetry/coach/short_prompt.py`** — Compact system prompt for local LLM models (5 rules + TTS rules, < 20 word target)

- **`dev/scripts/test_template_adapter.py`** — 95 assertions covering:
  - UtteranceMode and CoachMode.OFF enum values
  - CoachRunConfig defaults and overrides
  - Number spelling (1–10 → words, 11+ → digits)
  - Time formatting (0.03–5.0s, negative values)
  - Single loss/gain phrases (all 5 phases × variants)
  - Same-corner deduplication (3-phase loss, 2-phase gain)
  - Gain-first ordering
  - Empty facts → empty string
  - Fuel phrases (CRITICAL, WARNING, OK, UNKNOWN, margin >5, practice)
  - TTS output rules (spelled numbers, full units, no abbreviations)
  - Fixture-based integration tests (5 fixtures)
  - CLI `--utterance-mode template` on `generate_utterance.py`

- **`dev/scripts/test_template_adapter.js`** — Node.js wrapper following L12 pattern

### Modified files

- **`product/python/lap_telemetry/coach/coach_config.py`** — Added:
  - `UtteranceMode` enum: `CLOUD_LLM`, `LOCAL_LLM`, `TEMPLATE`
  - `CoachMode.OFF` to existing `CoachMode` enum
  - `utterance_mode: UtteranceMode` and `local_model: str` fields on `CoachRunConfig`

- **`product/python/lap_telemetry/coach/live_coach.py`** — Added:
  - `--coach-mode off` — skips CoachTap, SpeechQueue, TTS, starts recorder only
  - `--utterance-mode cloud-llm|local-llm|template` — routes to appropriate adapter
  - `--local-model MODEL` — specifies Ollama model for local-llm mode
  - Routing in `utterance_fn`, `corner_utterance_fn`, `fuel_utterance_fn` based on UtteranceMode
  - Startup message shows `utterance=cloud-llm|local-llm|template`

- **`product/python/lap_telemetry/coach/generate_utterance.py`** — Added:
  - `--utterance-mode` and `--local-model` CLI flags
  - Routes to `TemplateAdapter.generate()` for template mode
  - Routes to local Ollama via `_call_llm()` for local-llm mode

- **`package.json`** — Added `test_template_adapter.js` to `interactive-race-coach` feature tests

## Feature flags / config

- `CoachMode.OFF` — new value in `CoachMode` enum
- `UtteranceMode.CLOUD_LLM` — default, existing cloud LLM behavior
- `UtteranceMode.LOCAL_LLM` — routes to local Ollama on localhost:11434 with short prompt
- `UtteranceMode.TEMPLATE` — deterministic phrases, no network call
- `CoachRunConfig.local_model` — default `"llama3.2"`, overridden by `--local-model` or `COACH_LOCAL_MODEL` env var

## Deferred TODOs

- Streaming LLM tokens to TTS (future optimization)
- Auto-selecting utterance mode based on latency measurements
- Integration tests for `--coach-mode off` running the full recording pipeline (requires a sim)
- LOCAL_LLM mode tested only for CLI, not for live recording (needs `--once` smoke test with an Ollama instance)

## Test results

- 95/95 assertions pass in `test_template_adapter.py`
- 18/19 feature tests pass (pre-existing `test_facts_inspector.js` failure)
- Build succeeds (`npm run build`)