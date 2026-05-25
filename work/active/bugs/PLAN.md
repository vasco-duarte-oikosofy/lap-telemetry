# Mission: Bug Investigations

Active bug investigations. Each bug gets its own numbered slice folder.

---

## Bugs

| Slice | Bug | Status |
|---|---|---|
| `01-lusail-loading-error` | Large Lusail sessions throw "Maximum call stack size exceeded" in the loader | ✅ Moved to `work/completed/` |
| `02-ollama-auth` | Ollama cloud auth failure — 401 from `api.ollama.com/v1` with key set | ✅ Moved to `work/completed/` |
| `03-llm-reasoning-leak` | LLM outputs chain-of-thought instead of utterance — prompt guardrails too weak | 🔧 In progress |
| `04-contradictory-speed-coaching` | LLM coaches "slow down" when driver speed > reference speed at apex | 📋 Open |
| `05-utterance-ordering-lag` | Utterance appears 1–2 laps late — unknown bottleneck, need timing data | 📋 Open |
| `06-ghost-lap-comparator-crash` | 1-frame session-end laps crash compare_laps() with ValueError: max() arg is an empty sequence | 🔧 In progress |
| `07-coaching-reads-dropped-frames` | Coaching compares against incomplete live frame buffer (3093 vs 3935 frames for lap 14) — should read from the recorded session Parquet instead | 📋 Open |
| `08-coaching-data-source-mismatch` | compare.html reads full recorded Parquet; coaching pipeline reads live bus frames — same JS pipeline code, different (and inferior) data source | 📋 Open |
