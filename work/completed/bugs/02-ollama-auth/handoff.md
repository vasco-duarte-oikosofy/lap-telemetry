# Bug 02 Handoff

## State on disk

- `coach_config.toml` — `base_url` changed from `https://api.ollama.com/v1` → `https://ollama.com/v1`
- `product/python/lap_telemetry/coach/llm_adapter.py` — `_provider_base_url("ollama")` changed from `https://api.ollama.com/v1` → `https://ollama.com/v1`
- Full end-to-end test passed: `generate_utterance` with `glm-5.1:cloud` returns coaching text successfully.

## What was wrong

`api.ollama.com` is not the Ollama cloud API hostname (despite what the original bug description said). `ollama.com` is. The `api.ollama.com` domain redirects (301) and then rejects chat-completion requests with 401.

## What was fixed

Changed both the config file and the adapter's fallback URL to use `https://ollama.com/v1`.

## Deferred

- None. Bug is fully resolved.