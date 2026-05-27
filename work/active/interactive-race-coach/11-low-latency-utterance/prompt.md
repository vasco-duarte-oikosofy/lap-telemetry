# Slice 11: Deterministic vs. Network Utterance Generation

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

This slice adds two things to `live_coach.py` (the existing recorder-with-coach
CLI), alongside `--coach-mode`, `--coach-top`, `--tts-engine`, and
`--fuel-calls`:

1. **`--utterance-mode`** — choose between deterministic (local, no network)
   and network (LLM) utterance generation.
2. **`--coach-mode off`** — run the recorder without any coaching pipeline,
   producing only Parquet output.

Both are first-class CLI options, not separate programs or config workflows.

---

## Goal

### Utterance mode

Add a `--utterance-mode` CLI flag to `live_coach.py` (and to
`generate_utterance.py` for offline testing) with three values:

#### `cloud-llm` (default — current behaviour)

The current cloud LLM call via whatever model is configured in
`coach_config.toml`. This is the default so existing behaviour does not
change.

#### `local-llm`

Use a local, small LLM (e.g. `llama3.2`, `phi4-mini`, `qwen2.5:1.5b`) via
Ollama on `localhost:11434` with a tighter prompt contract (< 20 words,
single coaching point) for sub-5-second round-trips. The prompt adapts to
the smaller model's capabilities: shorter, more prescriptive, fewer rules.
A `--local-model` flag (default: `llama3.2`) selects which Ollama model to
use.

#### `template`

Skip the LLM entirely. Generate deterministic coaching phrases by filling
structured fact data into pre-defined templates. Zero LLM latency, fully
predictable, but less natural and less able to combine adjacent facts.

### Record-only mode (`--coach-mode off`)

The existing `--coach-mode` flag accepts `lap | turn | all`. Adding `off`
allows the driver to run the recorder without any coaching pipeline:

```bash
# Record a session with no coaching at all:
python3 -m lap_telemetry.coach.live_coach --out-dir sessions --coach-mode off
```

When `--coach-mode off`:
- The recorder starts and writes Parquet as normal.
- `CoachTap` is not started — no bus tap, no fact generation, no LLM calls,
  no TTS.
- Startup message prints `mode=off` to stderr.
- The `--utterance-mode`, `--coach-top`, `--tts-engine`, and `--fuel-calls`
  flags are still accepted but ignored (no coach tap to configure).

This is useful when the driver wants clean session recordings without any
coaching overhead, or when running on a machine without LLM/TTS setup.

---

## Architecture

```
UtteranceMode (enum)           CoachMode (enum, extended)
├── CLOUD_LLM  (default)        ├── LAP   (default)
├── LOCAL_LLM                    ├── TURN
└── TEMPLATE                     ├── ALL
                                 └── OFF   ← new
```

```
live_coach.py [--coach-mode lap|turn|all|off] [--utterance-mode cloud-llm|local-llm|template] [--local-model MODEL]
   │
   ├── --coach-mode off  →  recorder only, no CoachTap, no TTS, no LLM
   │
   └── --coach-mode lap|turn|all  →  CoachTap with utterance routing:
       │
       ├── CLOUD_LLM  →  utterance_fn()  →  generate_utterance(facts, llm_config)
       ├── LOCAL_LLM  →  utterance_fn()  →  generate_utterance(facts, local_llm_config, short_prompt)
       └── TEMPLATE   →  utterance_fn()  →  TemplateAdapter.generate(facts)
```

Both flags flow from CLI through `CoachRunConfig` into the pipeline. No new
process, no separate entry point — options on the existing command.

---

## Scope

### In scope

1. **`UtteranceMode` enum** in `coach_config.py`
   - Values: `CLOUD_LLM`, `LOCAL_LLM`, `TEMPLATE`.
   - Default: `CLOUD_LLM` (preserves current behaviour).
   - Added to `CoachRunConfig` as `utterance_mode: UtteranceMode`.
   - Added to `CoachRunConfig` as `local_model: str = "llama3.2"`.

2. **`CoachMode.OFF`** added to existing `CoachMode` enum in `coach_config.py`
   - Add `OFF = "off"` to the existing `CoachMode` enum (currently `LAP`, `TURN`, `ALL`).
   - When `--coach-mode off`, `live_coach.py` starts the recorder but skips
     creating `CoachTap`, the speech queue, and the TTS adapter entirely.
   - The bus is still created (so the recorder can write frames), but no tap
     consumes from it.
   - All coach-related flags (`--utterance-mode`, `--coach-top`, `--tts-engine`,
     `--fuel-calls`) are accepted but ignored.

3. **CLI flag `--utterance-mode`** in `live_coach.py` (the recorder-with-coach entry point)
   - `--utterance-mode cloud-llm|local-llm|template`
   - Default: `cloud-llm`.
   - Lives alongside `--coach-mode`, `--coach-top`, `--tts-engine`, `--fuel-calls`.
   - Stored in `CoachRunConfig`, passed through to `CoachTap` and utterance functions.
   - Also added to `generate_utterance.py` for offline testing.

4. **CLI flag `--local-model`** in `live_coach.py`
   - Specifies which local Ollama model to use for `--utterance-mode local-llm`.
   - Default: `llama3.2`.
   - Overrides `COACH_LOCAL_MODEL` env var.
   - Ignored for other utterance modes.

5. **Routing in utterance functions** in `live_coach.py`
   - `utterance_fn`, `corner_utterance_fn`, and `fuel_utterance_fn` check
     `CoachRunConfig.utterance_mode` and route to the appropriate adapter.
   - `CLOUD_LLM` → existing `generate_utterance()` call (unchanged).
   - `LOCAL_LLM` → `generate_utterance()` with overridden local config + short prompt.
   - `TEMPLATE` → `TemplateAdapter.generate(facts)` (no LLM call).

6. **`TemplateAdapter`** in `template_adapter.py` (new file)
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

7. **Short prompt for `LOCAL_LLM` mode** in `short_prompt.py` (new file)
   - A simpler, shorter system prompt targeting < 20 words.
   - Reduced rule count (5 rules instead of 13) for small models.
   - Same TTS output rules as the full prompt.
   - Used by `generate_utterance()` when `UtteranceMode.LOCAL_LLM` is active.

8. **Unit tests** (`dev/scripts/test_template_adapter.py` + `.js` wrapper)
   - TemplateAdapter: single loss → correct phrase.
   - TemplateAdapter: single gain → correct phrase.
   - TemplateAdapter: same-corner multiple losses → deduplicated phrase.
   - TemplateAdapter: gains before losses → correct ordering.
   - TemplateAdapter: empty facts → empty string.
   - TemplateAdapter: all TTS rules applied (numbers 1–10 spelled out, no
     abbreviations, full units).
   - UtteranceMode enum: default is CLOUD_LLM.
   - CoachMode enum: `OFF` value accepted.
   - CLI: `--utterance-mode` parses correctly on `live_coach.py`.
   - CLI: `--local-model` parses correctly on `live_coach.py`.
   - CLI: `--coach-mode off` starts recorder without coach tap.
   - CLI: `--utterance-mode` parses correctly on `generate_utterance.py`.
   - Integration: `generate_utterance()` with TEMPLATE mode returns template
     phrase, does not call LLM.
   - Integration: `generate_utterance()` with LOCAL_LLM mode constructs correct
     local config.
   - CLI: `live_coach.py --coach-mode off` produces no coaching output.
   - CLI: `live_coach.py --utterance-mode template` produces deterministic
     output without calling an LLM.
   - CLI: `live_coach.py --utterance-mode local-llm --local-model phi4-mini`
     routes to local Ollama.
   - CLI: `live_coach.py --utterance-mode cloud-llm` behaves identically to
     running without the flag (it's the default).

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

Template phrases use natural race-engineer language — the kind of thing
you'd hear over pit-to-car radio. They always **lead with time** (`loss_s`),
then add detail. See [`template-phrase-spec.md`](template-phrase-spec.md)
for the full specification including time formatting, delta interpretation,
and fuel phrases.

### Loss phrases (per phase)

| Phase | Phrase |
|---|---|
| `minimum_speed` | "You lost {time} at the apex of {corner_name}. You carried {speed_diff} kilometres per hour less." |
| `minimum_speed` + offset | "You lost {time} at the apex of {corner_name}. You carried {speed_diff} kilometres per hour less, and hit the apex {offset} metres {earlier/later}." |
| `entry` | "You lost {time} braking for {corner_name}. You lifted/braked {delta} metres {earlier/later}." |
| `entry` (no delta) | "You lost {time} going into {corner_name}." |
| `exit_brake` | "You lost {time} exiting {corner_name}. You released the brakes {delta} metres {earlier/later}." |
| `exit_throttle` | "You lost {time} getting on the power at {corner_name}. You got back on throttle {delta} metres {earlier/later}." |
| `exit` (generic) | "You lost {time} exiting {corner_name}. You carried less speed through." |

### Gain phrases (per phase)

| Phase | Phrase |
|---|---|
| `minimum_speed` | "You gained {time} at the apex of {corner_name}. You carried {speed_diff} kilometres per hour more." |
| `minimum_speed` + offset | "You gained {time} at the apex of {corner_name}. You carried {speed_diff} kilometres per hour more, hitting the apex {offset} metres {earlier/later}." |
| `entry` | "You gained {time} going into {corner_name}. You braked/lifted {delta} metres {earlier/later}." |
| `entry` (no delta) | "You gained {time} going into {corner_name}. You carried more speed into the corner." |
| `exit_brake` | "You gained {time} exiting {corner_name}. You released the brakes {delta} metres {earlier/later}." |
| `exit_throttle` | "You gained {time} getting on the power at {corner_name}. You got back on throttle {delta} metres {earlier/later}." |
| `exit` (generic) | "You gained {time} exiting {corner_name}. You carried more speed through." |

### Time formatting (`loss_s` → spoken English)

| `loss_s` (absolute) | Spoken as |
|---|---|
| 0.10 | "a tenth" |
| 0.20 | "two tenths" |
| 0.05 | "five hundredths" |
| 0.50 | "half a second" |
| 0.75 | "three quarters of a second" |
| 1.00 | "one second" |
| 1.20 | "one point two seconds" |

Full time formatting rules in [`template-phrase-spec.md`](template-phrase-spec.md).

### Same-corner deduplication

When the same corner has multiple loss phases, combine into one sentence.
The dominant phase (highest `loss_s`) leads; supporting phases are appended
as clauses connected with ", and":

> "You lost two tenths exiting turn three. You released the brakes four metres later, carried eleven kilometres per hour less through the apex, and got back on throttle nine metres later."

### Gain-first ordering

When both gains and losses exist, gains first, then losses, separated by
a full stop:

> "You gained a tenth at the apex of turn five. You carried three kilometres per hour more, and got back on throttle ten metres earlier. You lost two tenths exiting turn three. You released the brakes four metres later, carried eleven kilometres per hour less through the apex, and got back on throttle nine metres later."

---

## CLI usage

Both flags are first-class options on the recorder-with-coach command,
alongside the existing `--coach-mode`, `--coach-top`, `--tts-engine`, and
`--fuel-calls` flags:

```bash
# Record-only — no coaching at all, just Parquet output:
python3 -m lap_telemetry.coach.live_coach --out-dir sessions --coach-mode off

# Current default — cloud LLM (no flag change needed):
python3 -m lap_telemetry.coach.live_coach --out-dir sessions

# Deterministic templates (instant, no LLM, no network):
python3 -m lap_telemetry.coach.live_coach --out-dir sessions --utterance-mode template

# Fast local model (requires running Ollama locally):
python3 -m lap_telemetry.coach.live_coach --out-dir sessions --utterance-mode local-llm
python3 -m lap_telemetry.coach.live_coach --out-dir sessions --utterance-mode local-llm --local-model phi4-mini

# Combines naturally with other coach flags:
python3 -m lap_telemetry.coach.live_coach --out-dir sessions \
    --coach-mode all --coach-top 1 --utterance-mode template --fuel-calls
```

The `--utterance-mode` flag also works on the standalone utterance generator
for offline testing:

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

### Why `--coach-mode off` instead of a separate `record` entry point?

A separate `python3 -m lap_telemetry.recorder` entry point would work, but
`--coach-mode off` keeps one entry point (`live_coach.py`) for all recording
scenarios. It's one less command to remember, and it composes naturally with
`--out-dir`, `--once`, `--probe-timeout`, and `--debug`.

### Why a CLI flag, not a config file setting?

The driver may want to use `template` mode during practice (fast feedback)
and `cloud-llm` during debrief (richer phrasing) in the same session. A CLI
flag makes it easy to switch without editing `coach_config.toml`. The flag
also composes naturally with other CLI options like `--coach-mode` and
`--tts-engine`.

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
- [ ] `CoachMode.OFF` added to `CoachMode` enum in `coach_config.py`
- [ ] `CoachRunConfig` has `utterance_mode` and `local_model` fields
- [ ] `--coach-mode off` skips CoachTap, speech queue, and TTS adapter creation
- [ ] `--utterance-mode` and `--local-model` CLI flags on `live_coach.py`
- [ ] `--utterance-mode` and `--local-model` CLI flags on `generate_utterance.py`
- [ ] Utterance functions in `live_coach.py` route based on `CoachRunConfig.utterance_mode`
- [ ] `template_adapter.py` generates deterministic phrases from facts
- [ ] `short_prompt.py` provides a compact prompt for local models
- [ ] `CLOUD_LLM` mode produces identical output to current behaviour
- [ ] `TEMPLATE` mode produces deterministic phrases with correct dedup and ordering
- [ ] `LOCAL_LLM` mode uses local Ollama endpoint and short prompt
- [ ] `--coach-mode off` records Parquet with no coaching output
- [ ] Unit tests pass: `bash scripts/test-summary.sh --feature interactive-race-coach`
- [ ] `npm run build` succeeds
- [ ] Feature test list updated in `package.json`
- [ ] `handoff.md` and `learnings.md` created

## Definition of Done

- [ ] `UtteranceMode` enum, `CoachMode.OFF`, and `CoachRunConfig` fields in `coach_config.py`
- [ ] `--coach-mode off` skips coach tap in `live_coach.py`
- [ ] `--utterance-mode` and `--local-model` CLI flags on both `live_coach.py` and `generate_utterance.py`
- [ ] Routing logic in utterance functions based on mode
- [ ] `template_adapter.py` with gain/loss templates, dedup, ordering
- [ ] `short_prompt.py` for local LLM mode
- [ ] `test_template_adapter.py` + JS wrapper
- [ ] All tests green
- [ ] `handoff.md` + `learnings.md` written in this folder

## Non-goals

- Do not modify the cloud LLM prompt or model selection (current behaviour preserved).
- Do not implement streaming or partial TTS.
- Do not auto-select mode based on latency.
- Do not change the TTS adapter or speech queue.
- Do not add new fact types or modify fact structure.