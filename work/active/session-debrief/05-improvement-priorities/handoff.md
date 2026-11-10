# Handoff — Slice 05: improvement priorities

## State on disk

| File | Job |
|---|---|
| `product/python/lap_telemetry/session_priorities.py` | Scoring, per-corner dedupe, clause generation |
| `product/python/lap_telemetry/session_facts.py` | `SessionDebriefFacts.priorities` → payload `priorities` |
| `product/python/lap_telemetry/coach/facts.py` | exit-delta docstring corrected |

## API

```python
from lap_telemetry.session_priorities import build_priorities, suggest_change

priorities = build_priorities(laps, reference_corners)   # total_gap_s= override
p = priorities[0]
p.rank, p.corner_id, p.corner_name, p.phase, p.kind
p.recurring_loss_s, p.spread_s, p.share_of_gap, p.score
p.laps, p.laps_affected, p.suggestion, p.evidence
```

`kind` is `recurring` / `inconsistent` / `both`; the score is
`recurring_loss_s + 0.35 * spread_s`, so everything is in seconds per lap.

## What the current sessions say

Paul Ricard 3A (18 eligible, 16 clean): **corner "2"** is the top priority —
0.70 s on every lap, 23% of the mean 3.04 s gap, taken a gear higher and 27 km/h
down on the reference. Then Bretelle (1.51 s spread but only 0.29 s mean),
Pont (exit-brake, 7 km/h low onto the straight), Beausset 2, Beausset 1.

COTA (13 clean): exit_brake at turn 1, 0.54 s per lap.

## Rules worth preserving

- `recurring_loss_s` is the max over the corner's profitable phases; the
  headline phase is that one. Never sum phases — the windows overlap.
- Distances are clamped to ±60 m (`_MAX_PLAUSIBLE_DISTANCE_M`) before they
  become advice.
- Corner channels are aggregated per corner (`_aggregate_corners`): mode gear,
  median trail depth. Do not use a single lap's values.
- The fallback sentence ("losing X s here with no single measurable cause") is
  deliberate. Do not replace it with speculation.

## Tests

`dev/scripts/test_session_priorities.py` (+ `.js`), 36 assertions. Feature
suite: 665+ assertions across 22 scripts. Full suite now includes all six
debrief wrappers: **1925 passed, 4 pre-existing failures**.

## Next

Slice 06 renders these into `<session>_debrief.md`: top three priorities, the
clean-lap table, the envelope, and the excluded laps. Take `priorities[:3]` —
do not invent a new ranking in the renderer.
