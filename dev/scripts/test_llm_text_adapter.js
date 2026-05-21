/**
 * LLM text adapter tests.
 *
 * Tests the prompt templates, config loading, and LLM adapter
 * without making actual API calls.
 *
 * Run: node dev/scripts/test_llm_text_adapter.js
 */
// @parallel true

'use strict';

const { spawnSync } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function runPythonTests() {
  const code = `
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, r'''${path.join(ROOT, 'product', 'python')}''')

from lap_telemetry.coach.facts import LapComparisonFacts, CornerLoss
from lap_telemetry.coach.prompt_templates import build_messages, SYSTEM_PROMPT_TEMPLATE
from lap_telemetry.coach.coach_config import LLMConfig, load_config, _parse_simple_toml_llm, _parse_toml_value
from lap_telemetry.coach.generate_utterance import _load_facts_from_json, _dict_to_facts

# ─── Prompt template tests ───

def test_prompt_includes_word_limit():
    """System prompt includes the correct word limit from constraints."""
    facts = LapComparisonFacts(
        type="lap_coaching_summary",
        track_id="test",
        lap_number=1,
        lap_time_delta_s=0.5,
        top_losses=[],
        top_gains=[],
        constraints={"max_words": 35, "style": "calm_concise_engineer"},
    )
    messages = build_messages(facts)
    system_msg = [m for m in messages if m["role"] == "system"][0]
    assert "35" in system_msg["content"], f"Expected '35' in system prompt"
    print("  prompt_includes_word_limit: OK")

def test_prompt_includes_custom_word_limit():
    """System prompt uses custom word limit from constraints."""
    facts = LapComparisonFacts(
        type="lap_coaching_summary",
        track_id="test",
        lap_number=1,
        lap_time_delta_s=0.5,
        top_losses=[],
        top_gains=[],
        constraints={"max_words": 25, "style": "calm_concise_engineer"},
    )
    messages = build_messages(facts)
    system_msg = [m for m in messages if m["role"] == "system"][0]
    assert "25" in system_msg["content"], f"Expected '25' in system prompt"
    assert "35" not in system_msg["content"], f"Should not contain default '35'"
    print("  prompt_includes_custom_word_limit: OK")

def test_prompt_includes_same_corner_dedup():
    """System prompt tells the LLM how to merge same-corner items."""
    facts = LapComparisonFacts(
        type="lap_coaching_summary",
        track_id="test",
        lap_number=1,
        lap_time_delta_s=0.5,
        top_losses=[],
        top_gains=[],
    )
    messages = build_messages(facts)
    system_msg = [m for m in messages if m["role"] == "system"][0]
    content = system_msg["content"]
    assert "SAME-CORNER DEDUPLICATION" in content, "Missing SAME-CORNER DEDUPLICATION section"
    assert "combine into ONE" in content, "Missing same-corner merge instruction"
    print("  prompt_includes_same_corner_dedup: OK")

def test_prompt_includes_distance_delta_rules():
    """System prompt includes distance delta sign interpretation rules."""
    facts = LapComparisonFacts(
        type="lap_coaching_summary",
        track_id="test",
        lap_number=1,
        lap_time_delta_s=0.5,
        top_losses=[],
        top_gains=[],
    )
    messages = build_messages(facts)
    system_msg = [m for m in messages if m["role"] == "system"][0]
    content = system_msg["content"]
    assert "DISTANCE DELTA INTERPRETATION" in content, "Missing DISTANCE DELTA INTERPRETATION"
    assert "natural language" in content, "Missing natural language instruction"
    print("  prompt_includes_distance_delta_rules: OK")

def test_user_message_contains_facts():
    """User message contains the facts JSON."""
    facts = LapComparisonFacts(
        type="lap_coaching_summary",
        track_id="circuit-de-barcelona",
        lap_number=15,
        lap_time_delta_s=1.155,
        top_losses=[
            CornerLoss(
                corner_id="t3", corner_name="turn 3", apex_distance_m=1161.0,
                phase="minimum_speed", loss_s=0.19, driver_value=155.0,
                reference_value=165.6, unit="km/h", confidence="high",
            ),
        ],
        top_gains=[],
    )
    messages = build_messages(facts)
    user_msg = [m for m in messages if m["role"] == "user"][0]
    assert "turn 3" in user_msg["content"], "User message missing turn 3"
    assert "circuit-de-barcelona" in user_msg["content"], "User message missing track_id"
    assert "constraints" not in user_msg["content"], "Constraints should be excluded from user message"
    print("  user_message_contains_facts: OK")

def test_user_message_excludes_constraints():
    """User message does not include the constraints key."""
    facts = LapComparisonFacts(
        type="lap_coaching_summary",
        track_id="test",
        lap_number=1,
        lap_time_delta_s=0.5,
        top_losses=[],
        top_gains=[],
        constraints={"max_words": 35, "style": "calm_concise_engineer"},
    )
    messages = build_messages(facts)
    user_msg = [m for m in messages if m["role"] == "user"][0]
    user_data = json.loads(
        user_msg["content"].replace("Lap comparison facts:\\n", "").strip()
    )
    assert "constraints" not in user_data, "Constraints should not be in user message data"
    print("  user_message_excludes_constraints: OK")


# ─── Config loading tests ───

def test_load_config_defaults():
    """Default config values when no file exists."""
    # Temporarily clear env overrides
    env_backup = {}
    for key in ["COACH_LLM_PROVIDER", "COACH_LLM_MODEL", "COACH_CONFIG"]:
        if key in os.environ:
            env_backup[key] = os.environ.pop(key)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = load_config(Path(tmpdir) / "nonexistent.toml")
            assert cfg.provider == "anthropic", f"Expected anthropic, got {cfg.provider}"
            assert cfg.model == "claude-sonnet-4-20250514", f"Unexpected model: {cfg.model}"
            assert cfg.temperature == 0.3, f"Unexpected temperature: {cfg.temperature}"
            assert cfg.max_tokens == 100, f"Unexpected max_tokens: {cfg.max_tokens}"
    finally:
        os.environ.update(env_backup)

    print("  load_config_defaults: OK")

def test_load_config_from_toml():
    """Load config from a TOML file."""
    env_backup = {}
    for key in ["COACH_LLM_PROVIDER", "COACH_LLM_MODEL", "COACH_CONFIG"]:
        if key in os.environ:
            env_backup[key] = os.environ.pop(key)

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('[llm]\\nprovider = "openai"\\nmodel = "gpt-4o"\\ntemperature = 0.5\\nmax_tokens = 200\\napi_key_env = "OPENAI_API_KEY"\\n')
            f.flush()
            cfg = load_config(Path(f.name))
        assert cfg.provider == "openai", f"Expected openai, got {cfg.provider}"
        assert cfg.model == "gpt-4o", f"Expected gpt-4o, got {cfg.model}"
        assert cfg.temperature == 0.5, f"Expected 0.5, got {cfg.temperature}"
        assert cfg.max_tokens == 200, f"Expected 200, got {cfg.max_tokens}"
        assert cfg.api_key_env == "OPENAI_API_KEY", f"Unexpected api_key_env: {cfg.api_key_env}"
    finally:
        os.environ.update(env_backup)

    print("  load_config_from_toml: OK")

def test_env_var_overrides():
    """Env vars override config file values."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write('[llm]\\nprovider = "anthropic"\\nmodel = "claude-sonnet-4-20250514"\\n')
        f.flush()

    env_backup = {}
    for key in ["COACH_LLM_PROVIDER", "COACH_LLM_MODEL", "COACH_CONFIG"]:
        if key in os.environ:
            env_backup[key] = os.environ.pop(key)

    try:
        os.environ["COACH_LLM_PROVIDER"] = "deepseek"
        os.environ["COACH_LLM_MODEL"] = "deepseek-chat"
        cfg = load_config(Path(f.name))
        assert cfg.provider == "deepseek", f"Expected deepseek, got {cfg.provider}"
        assert cfg.model == "deepseek-chat", f"Expected deepseek-chat, got {cfg.model}"
    finally:
        for key in ["COACH_LLM_PROVIDER", "COACH_LLM_MODEL"]:
            os.environ.pop(key, None)
        os.environ.update(env_backup)

    print("  env_var_overrides: OK")

def test_api_key_from_env_var():
    """API key is read from the named environment variable, not config file."""
    env_backup = {}
    for key in ["COACH_LLM_PROVIDER", "COACH_LLM_MODEL", "COACH_CONFIG", "TEST_API_KEY_FOR_COACH"]:
        if key in os.environ:
            env_backup[key] = os.environ.pop(key)

    try:
        os.environ["TEST_API_KEY_FOR_COACH"] = "sk-test-key-12345"
        cfg = LLMConfig(api_key_env="TEST_API_KEY_FOR_COACH")
        assert cfg.api_key == "sk-test-key-12345", f"Expected test key, got {cfg.api_key}"
    finally:
        os.environ.pop("TEST_API_KEY_FOR_COACH", None)
        os.environ.update(env_backup)

    print("  api_key_from_env_var: OK")

def test_api_key_not_in_config():
    """API key should NOT be present when env var is not set."""
    env_backup = {}
    for key in ["NONEXISTENT_KEY_FOR_TEST"]:
        if key in os.environ:
            env_backup[key] = os.environ.pop(key)

    try:
        # Ensure the key is not set
        os.environ.pop("NONEXISTENT_KEY_FOR_TEST", None)
        cfg = LLMConfig(api_key_env="NONEXISTENT_KEY_FOR_TEST")
        assert cfg.api_key is None, f"Expected None, got {cfg.api_key}"
    finally:
        os.environ.update(env_backup)

    print("  api_key_not_in_config: OK")

def test_coach_config_env_path():
    """COACH_CONFIG env var specifies config file path."""
    env_backup = {}
    for key in ["COACH_LLM_PROVIDER", "COACH_LLM_MODEL", "COACH_CONFIG"]:
        if key in os.environ:
            env_backup[key] = os.environ.pop(key)

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('[llm]\\nprovider = "google"\\nmodel = "gemini-pro"\\n')
            f.flush()
            os.environ["COACH_CONFIG"] = f.name
            cfg = load_config()
            assert cfg.provider == "google", f"Expected google, got {cfg.provider}"
            assert cfg.model == "gemini-pro", f"Expected gemini-pro, got {cfg.model}"
    finally:
        os.environ.pop("COACH_CONFIG", None)
        os.environ.update(env_backup)

    print("  coach_config_env_path: OK")


# ─── Simple TOML parser tests ───

def test_simple_toml_parser():
    """Fallback TOML parser handles simple [llm] section."""
    text = """# comment
[llm]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.3
max_tokens = 100
api_key_env = "ANTHROPIC_API_KEY"
# base_url = ""
"""
    result = _parse_simple_toml_llm(text)
    assert result["provider"] == "anthropic"
    assert result["model"] == "claude-sonnet-4-20250514"
    assert result["temperature"] == 0.3
    assert result["max_tokens"] == 100
    assert result["api_key_env"] == "ANTHROPIC_API_KEY"
    print("  simple_toml_parser: OK")

def test_toml_value_parsing():
    """_parse_toml_value handles strings, ints, floats, bools."""
    assert _parse_toml_value('"hello"') == "hello"
    assert _parse_toml_value("42") == 42
    assert _parse_toml_value("3.14") == 3.14
    assert _parse_toml_value("true") is True
    assert _parse_toml_value("false") is False
    print("  toml_value_parsing: OK")


# ─── Facts loading tests ───

def test_load_facts_from_json():
    """Load LapComparisonFacts from canned JSON fixture."""
    fixture_path = r'${path.join(ROOT, 'dev', 'fixtures', 'coach', 'barcelona_lap15_facts.json')}'
    if not Path(fixture_path).exists():
        print("  load_facts_from_json: SKIP (fixture not found)")
        return

    facts = _load_facts_from_json(Path(fixture_path))
    assert facts.type == "lap_coaching_summary"
    assert facts.track_id == "circuit-de-barcelona"
    assert facts.lap_number == 15
    assert facts.lap_time_delta_s == 1.155
    assert len(facts.top_losses) == 3, f"Expected 3 losses, got {len(facts.top_losses)}"
    assert len(facts.top_gains) == 2, f"Expected 2 gains, got {len(facts.top_gains)}"

    # All losses are turn 3
    for loss in facts.top_losses:
        assert loss.corner_id == "t3", f"Expected t3, got {loss.corner_id}"

    # Loss phases include exit_brake, minimum_speed, exit_throttle
    phases = [l.phase for l in facts.top_losses]
    assert "exit_brake" in phases, f"Expected exit_brake in {phases}"
    assert "minimum_speed" in phases, f"Expected minimum_speed in {phases}"
    assert "exit_throttle" in phases, f"Expected exit_throttle in {phases}"

    print("  load_facts_from_json: OK")

def test_dict_to_facts_roundtrip():
    """LapComparisonFacts -> to_dict -> _dict_to_facts preserves key data."""
    facts = LapComparisonFacts(
        type="lap_coaching_summary",
        track_id="test-track",
        lap_number=7,
        lap_time_delta_s=0.82,
        top_losses=[
            CornerLoss(
                corner_id="t4", corner_name="turn 4", apex_distance_m=1650.0,
                phase="minimum_speed", loss_s=0.18, driver_value=95.0,
                reference_value=102.0, unit="km/h", confidence="high",
                exit_distance_delta_m=-8.0,
            ),
        ],
        top_gains=[],
        constraints={"max_words": 35, "style": "calm_concise_engineer"},
    )
    d = facts.to_dict()
    roundtrip = _dict_to_facts(d)
    assert roundtrip.track_id == "test-track"
    assert roundtrip.lap_number == 7
    assert roundtrip.lap_time_delta_s == 0.82
    assert len(roundtrip.top_losses) == 1
    assert roundtrip.top_losses[0].corner_id == "t4"
    assert roundtrip.top_losses[0].exit_distance_delta_m == -8.0
    print("  dict_to_facts_roundtrip: OK")


# ─── LLM adapter tests (no API calls) ───

def test_llm_adapter_missing_api_key():
    """generate_utterance raises error when API key is missing."""
    from lap_telemetry.coach.llm_adapter import generate_utterance, LLMAdapterError

    env_backup = {}
    for key in ["ANTHROPIC_API_KEY", "COACH_LLM_PROVIDER", "COACH_LLM_MODEL", "COACH_CONFIG"]:
        if key in os.environ:
            env_backup[key] = os.environ.pop(key)
    # Ensure no API key
    os.environ.pop("ANTHROPIC_API_KEY", None)

    try:
        facts = LapComparisonFacts(
            type="lap_coaching_summary",
            track_id="test",
            lap_number=1,
            lap_time_delta_s=0.5,
            top_losses=[],
            top_gains=[],
        )
        cfg = LLMConfig(api_key_env="ANTHROPIC_API_KEY")
        try:
            generate_utterance(facts, cfg)
            assert False, "Should have raised LLMAdapterError"
        except LLMAdapterError:
            pass
    finally:
        os.environ.update(env_backup)

    print("  llm_adapter_missing_api_key: OK")


# ─── Run all tests ───

test_prompt_includes_word_limit()
test_prompt_includes_custom_word_limit()
test_prompt_includes_same_corner_dedup()
test_prompt_includes_distance_delta_rules()
test_user_message_contains_facts()
test_user_message_excludes_constraints()
test_load_config_defaults()
test_load_config_from_toml()
test_env_var_overrides()
test_api_key_from_env_var()
test_api_key_not_in_config()
test_coach_config_env_path()
test_simple_toml_parser()
test_toml_value_parsing()
test_load_facts_from_json()
test_dict_to_facts_roundtrip()
test_llm_adapter_missing_api_key()
print("ALL OK")
`;
  return spawnSync('python3', ['-c', code], { encoding: 'utf8', timeout: 30000 });
}

function main() {
  console.log('═══ LLM Text Adapter Tests ═══\n');
  const res = runPythonTests();
  assert(!res.error, 'python llm tests spawned', res.error?.message || '');
  assert(res.status === 0, 'llm text adapter tests', res.status === 0 ? res.stdout.trim() : res.stderr.trim());
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) process.exit(1);
}

main();