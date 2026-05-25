# Bug 02: Ollama Cloud Auth Failure

## Status: ✅ Fixed

## Problem

Running `generate_utterance` with Ollama cloud returned `unauthorized` despite `OLLAMA_API_KEY` being set correctly.

## Root cause

`coach_config.toml` and `_provider_base_url()` in `llm_adapter.py` both pointed to `https://api.ollama.com/v1`. That hostname is **not** the Ollama cloud API — it returns a 301 redirect, and the redirect target rejects chat-completion requests with HTTP 401.

The correct hostname is `https://ollama.com/v1` (the same domain as the marketing site, but the `/v1` path serves the OpenAI-compatible API).

## Fix

Changed two files:
1. `coach_config.toml` — `base_url = "https://ollama.com/v1"`
2. `llm_adapter.py` — `_provider_base_url("ollama")` returns `"https://ollama.com/v1"`

## Verification

```bash
PYTHONPATH=product/python python3 -m lap_telemetry.coach.generate_utterance \
  --facts dev/fixtures/coach/barcelona_lap15_facts.json
# → Returns coaching text successfully
```