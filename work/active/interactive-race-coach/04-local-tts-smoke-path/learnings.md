# Learnings — Slice 04: Local TTS Smoke Path

## What surprised us

1. **Speech queue race condition is subtle.** The initial Queue-based
   implementation had a timing window: the worker could dequeue the
   "stale" item before `enqueue()` drained it. Switched to a single
   `_pending` slot with a lock, which atomically replaces the stale
   utterance. The worker always reads `_pending` under the lock.

2. **Idle event must be cleared on enqueue, not just on worker start.**
   If `flush()` is called immediately after `enqueue()`, the worker
   hasn't yet cleared the idle event, so `flush()` returns instantly
   before the text is spoken. Fix: `enqueue()` clears the idle event
   before waking the worker.

3. **The `_read_toml` refactor was needed.** The original only returned
   `[llm]` section data. Refactored to return the full TOML dict and
   updated `load_config` to extract `.get("llm", {})`. The backward-
   compatible alias `_parse_simple_toml_llm` keeps existing tests working.

4. **Pre-existing test bug.** `test_llm_text_adapter.js` had
   `max_tokens == 100` but the code default was 4096 (changed in
   ef942eb). Fixed during this slice's refactor commit.

5. **CLI subprocess test needs PYTHONPATH.** Running
   `python -m lap_telemetry.coach.speak` as a subprocess requires
   `PYTHONPATH` set to `product/python/` because the module isn't
   installed as a package.

6. **File adapter writes UTF-8 text, not real WAV.** For CI, the
   FileAdapter just writes the text content to the output file. This
   is intentional — it validates the pipeline without needing actual
   TTS synthesis.

7. **Kokoro is the primary engine.** Piper (and similar flat
   phoneme-level engines) sounds robotic with zero natural intonation.
   Kokoro (kokoro-onnx) with bm_daniel voice produces noticeably
   better output. It's now the default engine.
   Voice quality is still not perfect — sub-slice 04b.1 continues
   evaluation of ChatTTS, Qwen3-TTS, and XTTS-v2.

8. **Kokoro model loads lazily.** KokoroAdapter loads the model on
   first `speak()` call, not at construction time. This avoids the
   ~1s model load time at startup until it's actually needed.

9. **Edge TTS reads SSML tags as literal text.** Microsoft's Edge
   Read Aloud API does not support SSML. Tags like `<prosody>` are
   spoken verbatim.

10. **"m" abbreviation problem.** LLM-generated utterances use
    abbreviations like "4m later" which TTS engines read as "four em
    later" instead of "four meters later". Text preprocessing will
    be needed in a future slice.

## For the next agent

- `speech_queue.py` uses `threading.Event` + a single `_pending` slot.
  The worker re-checks `_pending` after each speak completes, so
  items queued during playback are not missed.
- `create_adapter(config)` is the factory — always use it to create
  adapters from config rather than constructing directly.
- `KokoroAdapter` lazy-loads the model on first use. If you change
  config, construct a new adapter.
- Voice quality evaluation continues in sub-slice 04b.1.
  Engines to evaluate: ChatTTS, Qwen3-TTS, XTTS-v2.
- The `sounddevice` package is installed. KokoroAdapter plays via
  sounddevice with WAV fallback for platforms without it.
- Text preprocessing for abbreviations ("4m" → "4 meters") is a
  known gap, documented in sub-slice 04b.1.