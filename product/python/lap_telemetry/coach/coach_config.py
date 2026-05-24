"""Coach configuration loader.

Reads provider/model settings from a TOML config file + env var overrides.
API keys are NEVER stored in the config file — only the name of the
environment variable that holds the key.
"""
from __future__ import annotations

import enum
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class CoachMode(enum.Enum):
    """When the coach speaks: after lap only, turn-by-turn, or both."""
    LAP = "lap"
    TURN = "turn"
    ALL = "all"


DEFAULT_CONFIG_PATHS = [
    Path("coach_config.toml"),
]


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key_env: str = "ANTHROPIC_API_KEY"
    temperature: float = 0.3
    max_tokens: int = 4096
    base_url: str | None = None

    @property
    def api_key(self) -> str | None:
        """Read the API key from the named environment variable."""
        return os.environ.get(self.api_key_env)


@dataclass
class CoachRunConfig:
    """Run-time configuration for the coaching pipeline."""
    mode: CoachMode = CoachMode.LAP
    top: int = 3


@dataclass
class TTSConfig:
    """TTS engine configuration."""
    engine: str = "kokoro"
    kokoro_model: str = "product/data/tts-voices/kokoro-v1.0.int8.onnx"
    kokoro_voices: str = "product/data/tts-voices/kokoro-voices-v1.0.bin"
    kokoro_voice: str = "bm_daniel"               # default voice
    kokoro_speed: float = 1.05                          # speaking speed
    output_file: str = "coach_output.wav"


def load_tts_config(config_path: Path | None = None) -> TTSConfig:
    """Load TTS configuration from TOML file with env var overrides.

    Args:
        config_path: Path to config file. If None, checks COACH_CONFIG env var,
            then falls back to coach_config.toml in the current directory.

    Returns:
        TTSConfig with resolved values.
    """
    path = _resolve_config_path(config_path)
    toml_data = _read_toml(path)
    tts = toml_data.get("tts", {})

    cfg = TTSConfig(
        engine=tts.get("engine", TTSConfig.engine),
        kokoro_model=tts.get("kokoro_model", TTSConfig.kokoro_model),
        kokoro_voices=tts.get("kokoro_voices", TTSConfig.kokoro_voices),
        kokoro_voice=tts.get("kokoro_voice", TTSConfig.kokoro_voice),
        kokoro_speed=float(tts.get("kokoro_speed", TTSConfig.kokoro_speed)),
        output_file=tts.get("output_file", TTSConfig.output_file),
    )

    # Env var overrides take precedence
    if os.environ.get("COACH_TTS_ENGINE"):
        cfg.engine = os.environ["COACH_TTS_ENGINE"]
    if os.environ.get("COACH_KOKORO_MODEL"):
        cfg.kokoro_model = os.environ["COACH_KOKORO_MODEL"]
    if os.environ.get("COACH_KOKORO_VOICES"):
        cfg.kokoro_voices = os.environ["COACH_KOKORO_VOICES"]
    if os.environ.get("COACH_KOKORO_VOICE"):
        cfg.kokoro_voice = os.environ["COACH_KOKORO_VOICE"]
    if os.environ.get("COACH_TTS_OUTPUT_FILE"):
        cfg.output_file = os.environ["COACH_TTS_OUTPUT_FILE"]

    return cfg


def load_config(config_path: Path | None = None) -> LLMConfig:
    """Load LLM configuration from TOML file with env var overrides.

    Args:
        config_path: Path to config file. If None, checks COACH_CONFIG env var,
            then falls back to coach_config.toml in the current directory.

    Returns:
        LLMConfig with resolved values.
    """
    path = _resolve_config_path(config_path)
    toml_data = _read_toml(path)
    llm = toml_data.get("llm", {})

    cfg = LLMConfig(
        provider=llm.get("provider", LLMConfig.provider),
        model=llm.get("model", LLMConfig.model),
        api_key_env=llm.get("api_key_env", LLMConfig.api_key_env),
        temperature=float(llm.get("temperature", LLMConfig.temperature)),
        max_tokens=int(llm.get("max_tokens", LLMConfig.max_tokens)),
        base_url=llm.get("base_url") or None,
    )

    # Env var overrides take precedence
    if os.environ.get("COACH_LLM_PROVIDER"):
        cfg.provider = os.environ["COACH_LLM_PROVIDER"]
    if os.environ.get("COACH_LLM_MODEL"):
        cfg.model = os.environ["COACH_LLM_MODEL"]

    return cfg


def _resolve_config_path(config_path: Path | None) -> Path | None:
    """Resolve which config file to use."""
    if config_path is not None:
        return config_path
    env_path = os.environ.get("COACH_CONFIG")
    if env_path:
        return Path(env_path)
    for p in DEFAULT_CONFIG_PATHS:
        if p.exists():
            return p
    return None


def _read_toml(path: Path | None) -> dict[str, Any]:
    """Read a TOML file and return the full data dict.

    Uses tomllib (Python 3.11+) or falls back to a simple hand parser.
    Returns {} if path is None or doesn't exist.
    """
    if path is None or not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")

    try:
        import tomllib
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return data
    except ImportError:
        pass

    # Simple fallback parser for flat sections
    return _parse_simple_toml(text)


def _parse_simple_toml(text: str) -> dict[str, Any]:
    """Minimal TOML parser for flat top-level sections.

    Handles: [section], key = "value", key = 123, key = 0.3, # comments.
    Returns nested dict keyed by section name.
    """
    result: dict[str, Any] = {}
    current_section: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[[") :
            current_section = stripped[1:-1].strip()
            if current_section not in result:
                result[current_section] = {}
            continue

        if current_section and "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip()
            # Remove inline comments
            if "#" in value:
                value = value[:value.index("#")].strip()
            result[current_section][key] = _parse_toml_value(value)

    return result


# Backward-compatible alias for tests that imported the old name;
# returns only the [llm] section as a flat dict.
def _parse_simple_toml_llm(text: str) -> dict[str, Any]:
    return _parse_simple_toml(text).get("llm", {})


def _parse_toml_value(value: str) -> Any:
    """Parse a simple TOML value: string, int, float, bool."""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value