# Slice 3: LLM Text Adapter with Canned Facts

## Goal

Build an LLM adapter that takes a `LapComparisonFacts` JSON object and a
prompt contract, sends them to a configured cloud model, and returns one
concise coaching utterance. This validates that provider configuration and
the prompt contract work without live telemetry complexity.

## Architecture risk validated

Can a cloud LLM produce useful, concise, fact-grounded coaching utterances
from our deterministic facts JSON? Can provider/model configuration be
managed locally without depending on pi's auth system?

## User-visible result

CLI command that loads canned facts (from a JSON file or by running the
existing fact generator), sends them to a configured LLM, and prints the
returned utterance.

Example:
```bash
python3 -m lap_telemetry.coach.generate_utterance \
  --facts dev/fixtures/coach/barcelona_lap15_facts.json \
  --track-config product/data/track-coaching/circuit-de-barcelona_dkr-engineering-4-elms25.json
```

Output:
```
Lost two tenths in turn 3 — exit speed 12 km/h lower, released brakes 4 m later. Protect exit speed there.
```

## Scope

### In scope

1. **LLM adapter module** (`lap_telemetry/coach/llm_adapter.py`)
   - Accepts `LapComparisonFacts` and a prompt contract
   - Calls a configured cloud LLM provider
   - Returns one utterance string
   - Logs the full input/output pair for debugging

2. **Provider configuration** (`coach_config.toml` or env vars)
   - Provider name (anthropic, openai, deepseek, google, etc.)
   - Model name
   - API key (from env var or config file — NOT pi's auth.json)
   - Optional: base URL (for custom/local endpoints)
   - Temperature, max_tokens
   - Config resolution: env vars override config file

3. **Prompt contract** (system prompt template)
   - Defines the LLM's role: calm race engineer
   - Constrains output: ≤35 words, mention ≤3 coaching points
   - Forbids hallucination: only use values from the supplied JSON
   - Handles same-corner deduplication (see below)
   - Handles entry/exit distance delta sign interpretation

4. **CLI entry point** (`generate_utterance`)
   - Takes `--facts` (path to JSON file) or `--lap` (runs fact generator)
   - Takes `--track-config` (path to track coaching JSON)
   - Prints the utterance to stdout
   - Prints the full facts JSON + utterance to a debug log

5. **Canned facts fixture**
   - `dev/fixtures/coach/barcelona_lap15_facts.json` — the output of
     `demo_coach_slice01.py` for reproducible testing

6. **Demo script** (`product/python/demo_coach_slice03.py`)
   - Similar pattern to `demo_coach_slice01.py` — runs the full pipeline
     end-to-end with default Barcelona fixtures, no manual setup needed.
   - Generates facts from the current/reference parquets (same as slice 01
     demo), then sends them through the LLM adapter to produce an utterance.
   - Also accepts `--facts` for canned JSON input (skips fact generation).
   - Prints the facts JSON followed by the utterance.
   - Usage: `python3 product/python/demo_coach_slice03.py`
   - With custom paths: `python3 product/python/demo_coach_slice03.py --current-lap <path> --reference-lap <path> --track-model <path>`
   - With canned facts: `python3 product/python/demo_coach_slice03.py --facts dev/fixtures/coach/barcelona_lap15_facts.json`
   - Requires: Python 3.10+, pyarrow, litellm (or openai), and a valid
     LLM API key in the environment (e.g. `ANTHROPIC_API_KEY`).

### Out of scope

- Live telemetry integration (slice 5)
- TTS (slice 4)
- Race engineer facts (fuel, strategy — slice 8+)
- Custom provider implementations beyond what `litellm` or `openai` SDK offers
- Voice cloning, voice selection
- Prompt optimization / A/B testing of prompt variants

## Same-corner deduplication

The data layer may produce multiple entries for the same corner (e.g. t3's
`exit_brake`, `minimum_speed`, and `exit_throttle` — all losses; t5's
`minimum_speed` and `exit` — both gains). The prompt contract must instruct
the LLM to:

1. When the same corner appears with multiple loss phases, say it once and
   reference the dominant phase. The other phases are supporting detail.
   Example: "Lost two tenths in turn 3 exit — minimum speed 10 km/h lower,
   released brakes 4 m later." (not: "Lost in turn 3 exit_brake. Also lost
   in turn 3 minimum_speed. Also lost in turn 3 exit_throttle.")

2. When the same corner appears with multiple gain phases, say it once about
   the exit. The `minimum_speed` gain is upstream of the exit gain — it's the
   root cause, not a separate coaching item.
   Example: "Gained a tenth in turn 5 exit — carried more speed through apex,
   back to full throttle 10 m earlier."

3. Never mention more than 2–3 corners total. Prioritize by `loss_s` magnitude.

See `docs/specs/interactive-race-coach-and-engineer.md` section
"Same-corner overlapping phases — prompt-layer deduplication."

## Distance delta sign interpretation

The prompt must help the LLM interpret distance deltas correctly:

| Phase | Field | Positive | Coaching language |
|-------|-------|----------|-------------------|
| entry | `entry_distance_delta_m` | Driver lifted/braked earlier | "you lifted X m earlier than reference" |
| entry | `entry_distance_delta_m` | Driver lifted/braked later (negative) | "you carried X m more speed into the corner" |
| exit | `exit_distance_delta_m` | Driver exited earlier (brake/throttle) | "you got back to full throttle X m earlier" |
| exit | `exit_distance_delta_m` | Driver exited later (negative) | "you released brakes X m later than reference" |

The sign convention is: `delta = reference_distance - driver_distance`.
The LLM should NOT expose the sign to the driver — always translate to
natural language.

## Provider configuration format

Use a simple TOML config file (`coach_config.toml`) in the project root or
a path specified by `COACH_CONFIG` env var. Environment variables override
config file values.

```toml
[llm]
provider = "anthropic"          # anthropic, openai, deepseek, google
model = "claude-sonnet-4-20250514"
api_key_env = "ANTHROPIC_API_KEY"  # env var name (NOT the key itself)
temperature = 0.3
max_tokens = 100
# base_url = ""                # optional: for local/custom endpoints
```

Environment variable overrides:
- `COACH_LLM_PROVIDER` overrides `provider`
- `COACH_LLM_MODEL` overrides `model`
- The API key is always read from the env var named in `api_key_env`
  (e.g. `ANTHROPIC_API_KEY`)

**No API keys stored in config files.** Only the *name* of the environment
variable is stored. The user sets the actual key in their shell environment.

## Dependencies

Use `litellm` as the LLM call layer — it provides a unified interface across
all major providers (Anthropic, OpenAI, DeepSeek, Google, etc.) with a
single `completion()` call. This avoids writing per-provider adapter code.

If `litellm` is too heavy or unstable, fall back to the `openai` SDK with
compatible endpoints (most providers support the OpenAI chat completions
format with a custom `base_url`).

## Prompt contract template

The system prompt should be a stable template in
`product/python/lap_telemetry/coach/prompt_templates.py`. It receives the
`constraints` from `LapComparisonFacts` and produces the final system + user
messages.

Key rules embedded in the system prompt:
1. You are a calm race engineer speaking to the driver during practice.
2. Summarize only the supplied facts JSON. Do not invent telemetry values.
3. Keep it under `max_words` words (default 35).
4. Use turn names from the JSON (e.g. "turn 3", not "the third corner").
5. Mention at most 2–3 coaching points, prioritized by `loss_s` magnitude.
6. When the same corner has multiple phases, combine into one coaching point
   about that corner's exit. Don't repeat the corner.
7. For distance deltas, translate to natural language (never show raw signs).
8. Prefer actionable language: what happened, where, what to try next.
9. If all confidence levels are low, say less.

## Testing

### Unit tests

1. **Prompt template rendering** — verify the system prompt includes the
   correct word limit and constraints from the facts JSON.
2. **Same-corner merging in prompt instructions** — verify the prompt tells
   the LLM how to merge same-corner items.
3. **Config loading** — verify config reads from TOML, env vars override.
4. **API key resolution** — verify key is read from the named env var, not
   from the config file.

### Integration tests (behind env var gate)

5. **End-to-end with real LLM** — `COACH_LLM_PROVIDER=anthropic` set,
   send Barcelona facts, verify utterance is ≤35 words, mentions turn 3,
   does not fabricate corners.
   This test is a smoke test, not CI. Document how to run it manually.

### Golden test

6. **Canned facts → utterance** — save the facts JSON fixture and the LLM
   response as a golden pair. Not strict match (LLM output varies), but
   verify structural constraints: word count, corner references, no
   hallucinated data.

## Acceptance criteria

- `llm_adapter.py` accepts `LapComparisonFacts` and returns an utterance string.
- Provider is configurable via TOML file + env vars, no keys in files.
- Prompt contract enforces ≤35 words, fact-only, same-corner deduplication.
- `generate_utterance` CLI works with `--facts` (canned JSON).
- Full facts + utterance logged for debugging.
- Unit tests pass (`bash scripts/test-summary.sh`).
- `npm run build` succeeds.
- `handoff.md` and `learnings.md` created.

## Non-goals

- Do not build the live telemetry pipeline (that's slice 5).
- Do not build TTS (that's slice 4).
- Do not optimize the prompt for specific models (future work).
- Do not A/B test prompt variants (future work).
- Do not add streaming/chunking to the LLM call (unnecessary for ≤35 words).
- Do not reuse pi's auth/config system — keep this self-contained.

## Definition of Done

- [ ] `llm_adapter.py` implemented
- [ ] `coach_config.toml` schema defined and loadable
- [ ] `prompt_templates.py` with system prompt template
- [ ] `generate_utterance` CLI entry point works
- [ ] Barcelona canned facts fixture saved
- [ ] Unit tests pass
- [ ] Manual smoke test with real LLM documented
- [ ] Full test suite passes
- [ ] Build succeeds
- [ ] `handoff.md` and `learnings.md` written