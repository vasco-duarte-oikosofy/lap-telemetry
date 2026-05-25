# Slice 10 handoff

## What was done

Added `--print-facts` flag to `generate_utterance.py`. When set, facts are
printed as pretty JSON to stdout and the process exits 0 without touching
the LLM.

## Files changed

- `product/python/lap_telemetry/coach/generate_utterance.py` — new `--print-facts`
  argument + early-exit block before the LLM call
- `dev/scripts/test_facts_inspector.py` — 7 unit assertions (no sim, no LLM)
- `dev/scripts/test_facts_inspector.js` — Node wrapper (uses `python`, not `python3`)
- `package.json` — `test_facts_inspector.js` added to `interactive-race-coach` array
- `work/active/interactive-race-coach/PLAN.md` — slice 10 row added

## Usage

```powershell
# inspect facts from a fixture
python -m lap_telemetry.coach.generate_utterance `
    --facts dev/fixtures/coach/barcelona_lap15_facts.json `
    --print-facts

# inspect facts derived from parquet files (no LLM call)
python -m lap_telemetry.coach.generate_utterance `
    --lap `
    --current-lap  <current>.parquet `
    --reference-lap <ref>.parquet `
    --track-config  <model>.json `
    --print-facts
```

Output pipes cleanly to `jq` or `python -m json.tool`.

## Status

Complete. All 8 assertions pass.
