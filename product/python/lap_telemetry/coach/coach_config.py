"""Coach configuration loader.

Reads provider/model settings from a TOML config file + env var overrides.
API keys are NEVER stored in the config file — only the name of the
environment variable that holds the key.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
class TTSConfig:
    """TTS engine configuration."""
    engine: str = "piper"
    piper_binary: str = "piper"
    piper_model: str | None = None
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
        piper_binary=tts.get("piper_binary", TTSConfig.piper_binary),
        piper_model=tts.get("piper_model") or None,
        output_file=tts.get("output_file", TTSConfig.output_file),
    )

    # Env var overrides take precedence
    if os.environ.get("COACH_TTS_ENGINE"):
        cfg.engine = os.environ["COACH_TTS_ENGINE"]
    if os.environ.get("COACH_PIPER_BINARY"):
        cfg.piper_binary = os.environ["COACH_PIPER_BINARY"]
    if os.environ.get("COACH_PIPER_MODEL"):
        cfg.piper_model = os.environ["COACH_PIPER_MODEL"]
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