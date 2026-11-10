# Handoff — Slice 02: per-lap debrief facts

## State on disk

| File | Job |
|---|---|
| `product/python/lap_telemetry/session_inputs.py` | Resolve (track, car) → reference + coaching model; read the reference **once**; certify its baseline time |
| `product/python/lap_telemetry/session_facts.py` | Build the `SessionDebriefFacts` payload (laps, phases, excluded) |
| `product/python/lap_telemetry/debrief.py` | CLI orchestration: `--list`, `--json`, the five-lap gate, overrides |
| `product/python/lap_telemetry/coach/lap_comparator.py` | `compare_lap_tables` gained `reject_implausibly_slow` (default true) |

Changed: `cli.py` (`--json`, `--reference`, `--track-model`, `--track`, `--car`),
`package.json` (feature suite now 20 scripts).

## Commands

```bash
bash scripts/test-summary.sh --feature session-debrief        # 20 scripts, 529 assertions
bash scripts/test-summary.sh                                   # 1553 passed, 4 pre-existing

PYTHONPATH=product/python python3 -m lap_telemetry debrief <session> --list
PYTHONPATH=product/python python3 -m lap_telemetry debrief <session> --json
```

Verified by hand on the Paul Ricard fixture: 25 segments, 19 eligible, 17 clean,
6 excluded, reference baseline 1:17.166, 19 laps × ~23 phases, ~151 KB JSON.
Lusail practice (4 eligible) exits 1 with "4 eligible lap(s); a debrief needs at
least 5" plus every rejected segment and its reason.

## API worth knowing about slice 03

```python
from lap_telemetry.session_source import load_session
from lap_telemetry.session_laps import classify_laps
from lap_telemetry.session_inputs import resolve_debrief_inputs
from lap_telemetry.session_facts import build_session_facts

session = load_session(path)
records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
inputs  = resolve_debrief_inputs(session)          # overrides available
facts   = build_session_facts(session, records, inputs)

facts.session      # SessionSummary: baselines, counts, combo, files
facts.laps         # list[LapFacts]: segment_index, lap_number, lap_time_s, delta_s,
                   #   clean, phases (list[CornerLoss], sorted by apex then phase)
facts.excluded     # list[ExcludedLap]: status, reason (inventory + unanalysable)
facts.to_dict()    # JSON-ready, schema_version "1"
```

- `LapFacts.phases` is **uncapped** and signed (`CornerLoss.loss_s`); slice 03
  should aggregate this list rather than re-running comparisons.
- `LapFacts.clean` comes from the inventory (within 5% of the fastest eligible
  lap). Slice 03's consistency work should use clean laps; the loss analysis
  legitimately includes slow ones.
- `session_inputs.reference_lap_time_s(table, path)` is the certified baseline.
  Use it anywhere a reference duration is needed.

## Deferred / next

- **Slice 03** (consistency): session-best baseline, optimal lap from best
  sectors. Sector times are still **not** extracted — the logic lives inside
  `summary.py:_run_file` and must be lifted into a reusable helper first.
- **Live coach baseline drift**: `compare_laps` re-derives the reference duration
  instead of using `reference_lap_time_s`, so its lap summary is up to ~1 s off
  from the debrief on 23 of 35 references. Deferred deliberately: fixing it
  changes spoken numbers. Worth a bug entry with the user's sign-off.
- No `--laps` filter, no output files, no report, no LLM yet (slices 05–08).
- `debrief` without `--list`/`--json` still exits 1 with "not implemented yet".
- Cost: 19 laps ≈ 4.5 s, dominated by one Node process per lap.
