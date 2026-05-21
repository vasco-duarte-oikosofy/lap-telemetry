# Sub-slice 04b.1: Find a TTS model that speaks naturally

## Problem

All TTS engines tested so far produce robotic, flat output with no
natural intonation. A race engineer coach must sound **assertive yet
patient** — like GP to Max Verstappen. The voice must convey urgency,
calmness, and confidence, not just read words in sequence.

## Engines tested

| Engine | Natural? | SSML? | Offline? | Result |
|--------|----------|-------|----------|--------|
| Piper | ❌ Flat, robotic | ❌ | ✅ | Rejected — zero prosody |
| Edge TTS | ⚠️ Decent voices | ❌ (tags read as text) | ❌ (needs internet) | Rejected — no SSML, needs net |
| Kokoro | ⚠️ Better than Piper | Partial (speed only) | ✅ | Last voice was "ok-ish" — needs more evaluation |
| pyttsx3 | ❌ Very robotic | ❌ | ✅ | Fallback only |

**Yet to evaluate:** ChatTTS, Qwen3-TTS, XTTS-v2

## Goal

Find a TTS engine + voice combination that sounds like a real person
speaking with natural intonation. The target persona is a Formula 1
race engineer: calm under pressure, clipped when urgent, reassuring
when strategic.

## Acceptance criteria

1. **Audition at least 3 engine+voice combos** against the GP phrase
   set below. Record each as a WAV/MP3 file in `artifacts/` for
   side-by-side comparison.

2. **Evaluate on these dimensions** (document in `learnings.md`):
   - Naturalness of intonation (does it sound human?)
   - Urgency / assertiveness (can it sound like "Box now, box now"?)
   - Calm reassurance (can it sound like "Well done for keeping your head"?)
   - Number handling (does "2.4" sound like "two point four" or "two dot four"?)
   - Latency (time from text to audio for a ≤35 word utterance)
   - Offline capability (can it run on Windows alongside LMU offline?)

3. **Select one engine+voice** and document the choice in `handoff.md`:
   - Engine name, version, install command
   - Voice name/id
   - Config parameters (speed, etc.)
   - Any text preprocessing needed (e.g., "4m" → "4 meters")

4. **If no engine passes**, document why each fails and propose next
   steps (e.g., fine-tuning, voice cloning, SSML-capable API).

## GP phrase set (use for all auditions)

```
GP_PHRASES = [
    "Gap is 2.4, gap is 2.4.",
    "Box this lap, box this lap. Medium tyre.",
    "Target 1:33.0, confirm 1:33.0.",
    "DRS available. Car 16 is 0.8 behind.",
    "You've got 8 laps remaining. Manage the rear.",
    "Tyre deg is looking reasonable. Push when you're ready.",
    "P2 is on here, Max. Assuming you can control the deg.",
    "Fastest lap is a 32.1. You are not concerned about that.",
    "Understood. Box now. Box now.",
    "Final lap, Max. Well done for keeping your head.",
]
```

## Engines to evaluate

### In scope

1. **Kokoro** (`kokoro-onnx`, already installed) — Evaluate **all**
   male voices: `am_adam`, `am_echo`, `am_eric`, `am_fenrir`,
   `am_liam`, `am_michael`, `am_onyx`, `am_puck`, `bm_daniel`,
   `bm_george`, `bm_fable`, `bm_lewis`. Try speed 0.9–1.1.

2. **Kokoro with speed/style tuning** — If Kokoro has per-utterance
   style control (pace, pitch), test it on urgent vs calm phrases.

3. **OpenAI TTS** (cloud, paid) — If `OPENAI_API_KEY` is available,
   test `echo` and `onyx` voices. These are known to be very natural.
   **Only if key is configured.** Cost is ~$0.015/request.

4. **Kokoro with text-level prosody hints** — Some engines respond to
   punctuation-driven prosody (ellipsis, dashes, ALL CAPS, trailing
   periods). Test whether inserting deliberate pauses/emphasis in the
   text itself improves delivery, e.g.:
   - `"Box this lap... Box this lap. Medium tyre."`
   - `"Understood. Box NOW. Box NOW."`

5. **ChatTTS** (`pip install ChatTTS`, https://github.com/2noise/ChatTTS)
   — Open-source TTS designed for natural dialogue with **intonation
   annotations**. Supports `[laugh]`, `[uv_break]`, `[lbreak]`,
   `[mbreak]`, and oral-burst markers like `[oral_0-9]` for prosody
   control. See demo: https://www.youtube.com/watch?v=MpVNZA6__3o
   Chinese-origin model with strong English support, runs on CPU.
   Key advantage: we can inject annotation tokens to make urgent
   phrases sound clipped and calm phrases sound reassured.
   Test with both plain text and annotated text, e.g.:
   - `"[lbreak]Box this lap[mbreak], box this lap. Medium tyre."`
   - `"[lbreak]Understood.[uv_break]Box NOW.[mbreak]Box NOW."`

6. **Qwen3-TTS** (https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice)
   — Qwen's newest TTS model with **instruction-based voice control**.
   You pass a natural language `instruct` like "Speak in a calm,
   assertive tone" alongside the text. Supports 9 built-in voices
   including `Ryan` ("Dynamic male voice with strong rhythmic drive",
   English native) and `Aiden` ("Sunny American male voice with a
   clear midrange", English native). Two model sizes:
   - **0.6B-CustomVoice** (~1.7 GB total: 1.3 GB model + 0.64 GB tokenizer)
   - **1.7B-CustomVoice** (~4.2 GB total: 3.5 GB model + 0.64 GB tokenizer)
   Key advantages:
   - Instruction-based prosody: `instruct="Speak with calm urgency"`
   - Streaming support (97ms first-token latency)
   - Per-utterance style control without SSML
   Key concerns:
   - Requires GPU (CUDA + bfloat16 recommended). CPU inference
     possible but very slow for 1.7B.
   - 0.6B model may be viable on CPU for short utterances.
   - `pip install qwen-tts` + torch + transformers ecosystem.
   Test with Ryan voice + instruct like:
   - `instruct="Speak with calm, assertive authority"`
   - `instruct="Urgent. Direct. Like a race engineer."`

7. **XTTS-v2** (by Coqui, https://huggingface.co/coqui/XTTS-v2)
   — The most downloaded TTS model on Hugging Face. Supports 17
   languages including English, with **voice cloning from a 3-second
   audio sample**. This means we could clone a race engineer voice
   from a short GP recording and use it for all coaching utterances.
   Key advantages:
   - Voice cloning: provide a 3+ second reference clip of a desired
     voice (e.g., GP, a calm assertive engineer) and it reproduces
     that timbre and style.
   - Natural prosody — trained on audiobook data, produces
     expressive, human-like intonation without annotations.
   - Multi-language, cross-lingual voice transfer.
   - 17 languages, ~1.8 GB model.
   Key concerns:
   - `pip install TTS` (Coqui TTS package) — heavy dependency chain
     (torch, etc.).
   - Inference speed: ~2x realtime on CPU, real-time on GPU.
     For ≤35 word utterances this should be acceptable.
   - Coqui (the company) shut down in 2024; the model is maintained
     by the community. License is CPML (non-commercial without
     agreement) — check if our use case qualifies.
   - Voice cloning quality varies with the reference clip.
   Test with:
   - Default voice (no cloning) for baseline naturalness
   - Cloned voice from a short GP/race-engineer audio clip if available
   - Speed 1.0 and 1.1x for pacing evaluation

### Out of scope

- Fine-tuning or voice cloning (future work)
- Streaming audio pipelines (unnecessary for ≤35 words)
- Building a custom model

## Constraints

- Must run on Windows alongside LMU without stealing GPU resources
- Must produce audio in < 500ms for a 35-word utterance (CPU inference)
- Must not require internet for the primary engine (cloud engines OK as
  fallback only, documented separately)

## Artifacts

Generate WAV files into `artifacts/`:
```
artifacts/
  kokoro_am_adam_phrase01.wav
  kokoro_am_onyx_phrase01.wav
  kokoro_bm_george_phrase01.wav
  kokoro_bm_daniel_phrase01.wav
  ...
```

Save a summary comparison table in `artifacts/comparison.md`.

## Parent slice dependency

This sub-slice depends on slice 04's TTS adapter architecture. The
chosen engine will be wired into `tts_adapter.py` as a new adapter
(e.g., `KokoroAdapter`, `EdgeTTSAdapter`, `OpenAITTSAdapter`) in a
follow-up slice.

## Definition of Done

- [ ] At least 3 engine+voice combos auditioned with GP phrases
- [ ] WAV artifacts saved to `artifacts/`
- [ ] Comparison table in `artifacts/comparison.md`
- [ ] One engine+voice selected with documented rationale
- [ ] Text preprocessing rules documented (abbreviation expansion)
- [ ] `handoff.md` and `learnings.md` written