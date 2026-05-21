"""LLM adapter for the race coach.

Takes a LapComparisonFacts object and a prompt contract, calls a
configured cloud LLM provider via litellm, and returns one concise
coaching utterance string.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from .coach_config import LLMConfig, load_config
from .facts import LapComparisonFacts
from .prompt_templates import build_messages

log = logging.getLogger(__name__)


class LLMAdapterError(Exception):
    """Raised when the LLM call fails."""


def generate_utterance(
    facts: LapComparisonFacts,
    config: LLMConfig | None = None,
) -> str:
    """Generate a coaching utterance from lap comparison facts.

    Args:
        facts: Structured lap comparison facts.
        config: LLM configuration. If None, loaded from default config.

    Returns:
        A single coaching utterance string.

    Raises:
        LLMAdapterError: If the LLM call fails.
    """
    if config is None:
        config = load_config()

    api_key = config.api_key
    if not api_key:
        raise LLMAdapterError(
            f"API key not found. Set the {config.api_key_env} environment variable."
        )

    messages = build_messages(facts)

    # Log full input for debugging
    log.debug("LLM input:\n%s", json.dumps(messages, indent=2))

    utterance = _call_llm(config, messages)

    # Log full output for debugging
    log.debug("LLM output: %s", utterance)

    # Also emit structured debug log
    log.info(
        "Coach utterance generated | facts=%s | utterance=%s",
        json.dumps(facts.to_dict()),
        json.dumps(utterance),
    )

    return utterance


def _call_llm(config: LLMConfig, messages: list[dict[str, str]]) -> str:
    """Call the LLM provider via litellm.

    Falls back to the openai SDK if litellm is not installed.
    """
    try:
        return _call_via_litellm(config, messages)
    except ImportError:
        log.debug("litellm not available, falling back to openai SDK")
        return _call_via_openai(config, messages)


def _call_via_litellm(config: LLMConfig, messages: list[dict[str, str]]) -> str:
    """Call the LLM via litellm's unified completion() API."""
    from litellm import completion  # type: ignore[import-untyped]

    kwargs: dict[str, Any] = {
        "model": f"{config.provider}/{config.model}",
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }

    # litellm reads API keys from standard env vars automatically
    # (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
    # But we set it explicitly to match our config's api_key_env
    api_key = config.api_key
    if api_key:
        kwargs["api_key"] = api_key

    if config.base_url:
        kwargs["api_base"] = config.base_url

    response = completion(**kwargs)

    content = response.choices[0].message.content  # type: ignore[union-attr]
    if content is None:
        raise LLMAdapterError("LLM returned empty content")

    return content.strip()


def _call_via_openai(config: LLMConfig, messages: list[dict[str, str]]) -> str:
    """Call the LLM via the OpenAI SDK with a custom base_url.

    Most providers support the OpenAI chat completions format with a
    custom base_url, so this works as a fallback.
    """
    from openai import OpenAI  # type: ignore[import-untyped]

    api_key = config.api_key
    if not api_key:
        raise LLMAdapterError(
            f"API key not found. Set the {config.api_key_env} environment variable."
        )

    # Determine base URL from provider
    base_url = config.base_url
    if not base_url:
        base_url = _provider_base_url(config.provider)

    kwargs: dict[str, Any] = {
        "api_key": api_key,
    }
    if base_url:
        kwargs["base_url"] = base_url

    client = OpenAI(**kwargs)

    response = client.chat.completions.create(
        model=config.model,
        messages=messages,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )

    content = response.choices[0].message.content
    if content is None:
        raise LLMAdapterError("LLM returned empty content")

    return content.strip()


def _provider_base_url(provider: str) -> str | None:
    """Return the default base URL for a known provider.

    Returns None for providers that use the SDK's default URL.
    """
    urls: dict[str, str] = {
        "deepseek": "https://api.deepseek.com",
        "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    }
    return urls.get(provider)