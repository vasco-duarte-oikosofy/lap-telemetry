# Bug 05: Coaching utterance arrives 1–2 laps after the triggering lap

## Observed

```
lap boundary -> lap 7
[utterance for lap 5 spoken here]
```

Lap 5 completed, but coaching was heard mid-lap 7.

## Root cause

Unknown — could be LLM API latency, Parquet conversion, `compare_laps()`, or TTS queue depth. Need per-step timings visible at normal (non-debug) log level.

## Fix plan

1. Promote the existing `log.info("Coaching: ... convert=%.1fms compare=%.1fms llm=%.1fms")` in `live_fact_generator.py` to `print(..., sys.stderr)` so it's visible without `--debug`.
2. Add wall-clock timestamps at `coach_tap._on_lap_completed` entry and at utterance enqueue so total pipeline latency is visible.

## Files

- `product/python/lap_telemetry/coach/live_fact_generator.py`
- `product/python/lap_telemetry/coach/coach_tap.py`

## Status

📋 Open — need timing data to locate bottleneck
