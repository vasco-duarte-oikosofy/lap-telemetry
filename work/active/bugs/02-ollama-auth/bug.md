# Bug 02: Ollama Cloud Auth Failure

## What we learned

- `coach_config.toml` had `base_url = "https://ollama.com/v1"` — the marketing site, not the API
- The correct Ollama cloud OpenAI-compatible endpoint is `https://api.ollama.com/v1`
- The URL is now fixed; requests reach the right endpoint and receive a proper HTTP 401
- The `openai` SDK is installed and the auth header format (`Authorization: Bearer <key>`) is correct
- `OLLAMA_API_KEY` is set in env and is being sent; the server rejects it

## What needs to be fixed

- Verify `OLLAMA_API_KEY` matches a key from the Ollama cloud dashboard (`ollama.com` → account → API keys)
- Verify `glm-5.1:cloud` is accessible on the account (may require a paid plan or explicit access)
