# Bug 05: Coaching utterance arrives 1–2 laps after the triggering lap

## Observed

```
lap boundary -> lap 7
[utterance for lap 5 spoken here]
```

Lap 5 completed, but coaching was heard mid-lap 7.

## Root cause

**Quantified:** Pipeline timing (3 runs with `glm-5.1:cloud`) shows:

| Stage | Avg | Min | Max |
|---|---|---|---|
| LLM round-trip | 48.5 s | 38.9 s | 64.8 s |
| TTS synthesis | 4.7 s | 4.3 s | 5.3 s |
| **Total (facts → audio starts)** | **53.3 s** | — | — |

LLM latency (91% of total) makes live coaching impractical. At ~50 km/h average, the driver is ~750 m past the event by the time audio starts. This is an architectural limitation, not a defect.

## Resolution

**Retired** — this is a feature, not a bug. Adding low-latency utterance modes (local LLM, template-based) is tracked as:

→ **Slice 11: `low-latency-utterance`** in `work/active/interactive-race-coach/11-low-latency-utterance/`

The `--utterance-mode local-llm|template|cloud-llm` option will let the driver choose speed vs. phrasing quality.

## Status

📋 Retired → see slice 11 (`low-latency-utterance`)
