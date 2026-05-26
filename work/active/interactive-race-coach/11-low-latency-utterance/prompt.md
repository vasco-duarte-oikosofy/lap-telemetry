# Slice 11: Low-Latency Utterance Options

## Context

Timing tests on the current coaching pipeline reveal that the round-trip from
facts to audible speech is dominated by the LLM call:

| Stage | Avg (3 runs) | Min | Max |
|---|---|---|---|
| LLM round-trip | 48.5 s | 38.9 s | 64.8 s |
| TTS synthesis | 4.7 s | 4.3 s | 5.3 s |
| **Total (facts → audio starts)** | **53.3 s** | — | — |
| Spoken utterance length | 11.3 s | 10.4 s | 12.9 s |

LLM latency accounts for **91%** of the total. The Kokoro TTS engine is
efficient (~5 s), but waiting nearly a minute for the LLM to reply makes
live coaching impractical: the driver may be in a completely different part
of the circuit by the time the utterance starts playing.

This slice introduces **two optional low-latency utterance modes** as
parameters on the recorder/coach CLI, so the driver can choose the strategy
that best fits their situation.

---

## Goal

Add two new `--utterance-mode` options to the coach pipeline:

### Mode 1: `local-llm`

Use a local, small LLM (e.g. `llama3.2`, `phi4-mini`, `qwen2.5:1.5b`) via
Ollama with a tighter prompt contract (< 20 words, single coaching point) for
sub-5-second round-trips. The prompt adapts to the smaller model's
capabilities: shorter, more prescriptive, fewer rules.

### Mode 2: `template`

Skip the LLM entirely. Generate deterministic coaching phrases by filling
structured fact data into pre-defined templates. Zero LLM latency, fully
predictable, but less natural and less able to combine adjacent facts.

### Mode 3: `cloud-llm` (default — current behaviour)

The current cloud LLM call via `glm-5.1:cloud` or whatever model is configured
in `coach_config.toml`. This is the default so existing behaviour does not
change.

---

## Architecture

```
UtteranceMode (enum)
├── CLOUD_LLM  →  existing pipeline (LLM call via litellm / openai)
├── LOCAL_LLM  →  same pipeline, but pointed at local Ollama model with tighter prompt
└── TEMPLATE   →  TemplateAdapter fills pre-defined phrases, no LLM call
```

```
generate_utterance()
   │
   ├── CLOUD_LLM  →  LLMAdapter (existing)
   ├── LOCAL_LLM  →  LLMAdapter with local config + short_prompt
   └── TEMPLATE   →  TemplateAdapter (new)
```

---

## Scope

### In scope

1. **`UtteranceMode` enum** in `coach_config.py`
   - Values: `CLOUD_LLM`, `LOCAL_LLM`, `TEMPLATE`.
   - Default: `CLOUD_LLM` (preserves current behaviour).

2. **CLI flag `--utterance-mode`** in `live_coach.py` and `record_with_coach.py`
   - `--utterance-mode cloud-llm|local-llm|template`
   - Default: `cloud-llm`.
   - Stored in `CoachRunConfig`.

3. **`TemplateAdapter`** in `template_adapter.py` (new file)
   - Implements the same interface as `generate_utterance(facts, config) -> str`.
   - Uses pre-defined phrase templates with fact interpolation.
   - Templates cover the known phases: `minimum_speed`, `entry`, `exit`,
     `exit_brake`, `exit_throttle`.
   - Each phase has a loss template and a gain template.
   - Same-corner deduplication: when the same corner has multiple losses,
     combine into a single utterance (same logic as the LLM prompt rules,
     but hard-coded).
   - Gain-first ordering: gains before losses, same as LLM prompt rules.
   - Unit expansion: `km/h` → `kilometres per hour`, `m` → `metres`, etc.
   - All TTS output rules from the LLM prompt are baked into the templates:
     numbers 1–10 spelled out, full units, no abbreviations, no em-dashes.
   - If facts are empty (no losses or gains), return an empty string.

4. **Short prompt for `LOCAL_LLM` mode** in `short_prompt.py` (new file)
   - A simpler, shorter system prompt targeting < 20 words.
   - Reduced rule count (5 rules instead of 13) for small models.
   - Same TTS output rules as the full prompt.
   - Used by `generate_utterance()` when `UtteranceMode.LOCAL_LLM` is active.

5. **`generate_utterance()` routing** in `llm_adapter.py`
   - When `UtteranceMode.CLOUD_LLM`: current behaviour (call configured model
     with full prompt).
   - When `UtteranceMode.LOCAL_LLM`: override config to use local Ollama
     endpoint (`http://localhost:11434/v1`) and a small model. Call with the
     short prompt. Model name is configurable via `--local-model` flag or
     `COACH_LOCAL_MODEL` env var (default: `llama3.2`).
   - When `UtteranceMode.TEMPLATE`: call `TemplateAdapter` instead of the LLM.

6. **`--local-model` flag** in `live_coach.py`
   - Specifies which local Ollama model to use for `--utterance-mode local-llm`.
   - Default: `llama3.2`.
   - Overrides `COACH_LOCAL_MODEL` env var.
   - Ignored for other utterance modes.

7. **Unit tests** (`dev/scripts/test_template_adapter.py` + `.js` wrapper)
   - TemplateAdapter: single loss → correct phrase.
   - TemplateAdapter: single gain → correct phrase.
   - TemplateAdapter: same-corner multiple losses → deduplicated phrase.
   - TemplateAdapter: gains before losses → correct ordering.
   - TemplateAdapter: empty facts → empty string.
   - TemplateAdapter: all TTS rules applied (numbers 1–10 spelled out, no
     abbreviations, full units).
   - UtteranceMode enum: default is CLOUD_LLM.
   - CLI: `--utterance-mode` parses correctly.
   - CLI: `--local-model` parses correctly.
   - Integration: `generate_utterance()` with TEMPLATE mode returns template
     phrase, does not call LLM.
   - Integration: `generate_utterance()` with LOCAL_LLM mode constructs correct
     local config.

### Out of scope

- Modifying the LLM prompt for `CLOUD_LLM` mode (current prompt stays as-is).
- Benchmarking or auto-selecting between modes based on latency. The driver
  chooses explicitly.
- Streaming LLM responses or partial TTS (future optimization).
- Changing the TTS pipeline or speech queue.
- Modifying `compare_laps()` or fact generation.
- Adding new fact types or track model data.

---

## Template phrases

Template phrases follow the same rules as the LLM prompt (gain-first,
same-corner dedup, TTS output rules) but are deterministic:

### Loss templates (per phase)

| Phase | Template |
|---|---|
| `minimum_speed` | "You lost time at {corner_name}. Minimum speed {driver_speed_diff} kilometres per hour lower." |
| `entry` | "You lost time at {corner_name} entry. Lifted {entry_delta} metres earlier." |
| `exit_brake` | "You lost time at {corner_name} exit. Released brakes {exit_delta} metres later." |
| `exit_throttle` | "You lost time at {corner_name} exit. Back on throttle {exit_delta} metres later." |
| `exit` | "You lost time at {corner_name} exit. Carried less speed through the apex." |

### Gain templates (per phase)

| Phase | Template |
|---|---|
| `minimum_speed` | "You gained time in {corner_name}. Carried more speed through the apex." |
| `entry` | "You gained time in {corner_name} entry. Carried more speed into the corner." |
| `exit_brake` | "You gained time in {corner_name} exit. Released brakes earlier." |
| `exit_throttle` | "You gained time in {corner_name} exit. Back on throttle {exit_delta} metres earlier." |
| `exit` | "You gained time in {corner_name} exit. Got back to full throttle earlier." |

### Same-corner deduplication

When the same corner has multiple loss phases, combine into one sentence:

> "You lost time at turn 3 exit. Minimum speed ten kilometres per hour lower, released brakes four metres later."

The dominant phase (highest `loss_s`) leads the sentence; supporting phases
are appended as clauses.

### Gain-first ordering

When both gains and losses exist:

> "You gained time in turn 5. Back on throttle ten metres earlier. You lost time at turn 3. Minimum speed ten kilometres per hour lower."

Gains before losses, separated by a full stop.

---

## CLI usage

```bash
# Current default — cloud LLM (no change):
python3 record_with_coach.py --out-dir sessions

# Fast local model:
python3 record_with_coach.py --out-dir sessions --utterance-mode local-llm
python3 record_with_coach.py --out-dir sessions --utterance-mode local-llm --local-model phi4-mini

# Instant deterministic templates:
python3 record_with_coach.py --out-dir sessions --utterance-mode template
```

The `--utterance-mode` flag also works with the standalone utterance generator:

```bash
# Template mode (instant, no LLM):
python3 -m lap_telemetry.coach.generate_utterance \
    --facts dev/fixtures/coach/barcelona_lap15_facts.json \
    --utterance-mode template

# Local LLM mode:
python3 -m lap_telemetry.coach.generate_utterance \
    --facts dev/fixtures/coach/barcelona_lap15_facts.json \
    --utterance-mode local-llm \
    --local-model llama3.2
```

---

## Design decisions

### Why not auto-detect?

The driver should choose explicitly. A cloud model may produce better phrasing
but is slow; a local model is fast but may hallucinate; templates are
deterministic but rigid. The tradeoff is personal and session-dependent.

### Why a simpler prompt for LOCAL_LLM?

Small models (1–3 B parameters) cannot reliably follow the 13-rule full
prompt. Reducing to 5 core rules + TTS output rules gives them a fighting
chance. The shorter prompt also produces shorter responses, cutting LLM
time further.

### Why templates at all?

Templates give **zero-latency** utterance generation (no network, no GPU).
For coaching during live sessions where reaction time matters more than
natural language, this is the right tradeoff. The templates encode the same
rules as the LLM prompt (gain-first, dedup, TTS output rules), so the
output is consistent with what the LLM would produce.

### Why not streaming?

Streaming LLM tokens to TTS (synthesize as the LLM generates) is a
compelling future optimization but requires architecture changes to both
the LLM adapter and the speech queue. It's out of scope for this slice.

---

## Acceptance criteria

- [ ] `UtteranceMode` enum with `CLOUD_LLM`, `LOCAL_LLM`, `TEMPLATE` in `coach_config.py`
- [ ] `--utterance-mode` and `--local-model` CLI flags in `live_coach.py`
- [ ] `template_adapter.py` generates deterministic phrases from facts
- [ ] `short_prompt.py` provides a compact prompt for local models
- [ ] `generate_utterance()` routes to the correct strategy based on `UtteranceMode`
- [ ] `CLOUD_LLM` mode produces identical output to current behaviour
- [ ] `TEMPLATE` mode produces deterministic phrases with correct dedup and ordering
- [ ] `LOCAL_LLM` mode uses local Ollama endpoint and short prompt
- [ ] Unit tests pass: `bash scripts/test-summary.sh --feature interactive-race-coach`
- [ ] `npm run build` succeeds
- [ ] Feature test list updated in `package.json`
- [ ] `handoff.md` and `learnings.md` created

## Definition of Done

- [ ] `UtteranceMode` enum and routing logic in `coach_config.py` / `llm_adapter.py`
- [ ] `template_adapter.py` with gain/loss templates, dedup, ordering
- [ ] `short_prompt.py` for local LLM mode
- [ ] `--utterance-mode` and `--local-model` flags added
- [ ] `generate_utterance.py` updated with new flags
- [ ] `test_template_adapter.py` + JS wrapper
- [ ] All tests green
- [ ] `handoff.md` + `learnings.md` written in this folder

## Non-goals

- Do not modify the cloud LLM prompt or model selection (current behaviour preserved).
- Do not implement streaming or partial TTS.
- Do not auto-select mode based on latency.
- Do not change the TTS adapter or speech queue.
- Do not add new fact types or modify fact structure.