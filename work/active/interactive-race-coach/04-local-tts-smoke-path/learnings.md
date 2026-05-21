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
   TTS synthesis. A real audio-producing FileAdapter would need Piper
   installed.

## For the next agent

- `speech_queue.py` uses `threading.Event` + a single `_pending` slot.
  The worker re-checks `_pending` after each speak completes, so
  items queued during playback are not missed.
- `create_adapter(config)` is the factory — always use it to create
  adapters from config rather than constructing directly.
- Piper is not installed on this machine. The PiperAdapter path is
  tested only for instantiation, not actual synthesis. Manual smoke
  testing with Piper requires installing Piper + a voice model.
- The `sounddevice` package is not installed. PiperAdapter's playback
  will fall back to the platform audio player (afplay on macOS).