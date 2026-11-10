# Slice 05: Improvement priorities

## Goal

Turn two rankings (slow every lap / erratic) plus the extended corner facts into
**one deduplicated list of things to change**, each with a deterministic,
computed suggestion. The coach and the report both read this list; nobody
re-derives it.

## User-visible result

```json
"priorities": [
  { "rank": 1, "corner_id": "t3", "corner_name": "Signes", "phase": "minimum_speed",
    "kind": "recurring", "recurring_loss_s": 0.61, "spread_s": 0.18,
    "share_of_gap": 0.16, "score": 0.67, "laps_affected": 15, "laps": 16,
    "suggestion": "one gear lower at the apex (5th, not 6th) and carry 5 km/h more minimum speed",
    "evidence": { "driver_value": 229.8, "reference_value": 234.8, "unit": "km/h",
                  "driver_gear": 6, "reference_gear": 5 } }
]
```

## Scope

### In scope

1. `product/python/lap_telemetry/session_priorities.py`:
   - `Priority` — one opportunity, with the numbers behind it.
   - `build_priorities()` — scores, deduplicates per corner, ranks, attaches a
     computed suggestion.
   - `suggest_change()` — pure function from facts to a sentence; no LLM.
2. `session_facts`: `SessionDebriefFacts.priorities`, serialized as
   `priorities`.

### Out of scope

- Rendering (slice 06), conversation (slice 07/08).

## Ranking

Everything is in **seconds per lap**, so the score is comparable and auditable:

```
recurring_loss_s = max(mean_loss_s) over the corner's profitable phases
spread_s         = spread of that corner's minimum-speed loss across clean laps
score            = recurring_loss_s + 0.35 * spread_s
share_of_gap     = recurring_loss_s / mean clean-lap delta to the reference
```

Recurring weight is higher because repeatable time is the money; spread is
weighted 0.35 because a corner you get right one lap in three is worth coaching
but not as much as one you lose every lap.

**Deduplicated per corner.** A corner can appear in both rankings and produce
four phase facts; the driver must not receive five homework items for turn 3.
One row per corner, headlined by its most expensive phase.

`kind` is `recurring` (mean loss, most laps affected), `inconsistent` (big
spread, little mean), or `both`.

## Suggestions (computed, never invented)

Clauses are generated in a fixed order from facts that already exist, and the
first two that apply are joined:

| Condition | Clause |
|---|---|
| driver gear ≠ reference gear at the apex | `one gear lower at the apex (5th, not 6th)` |
| speed deficit ≥ 1 km/h at minimum speed | `carry 4 km/h more minimum speed` |
| entry ≥ 3 m earlier than the reference | `brake 12 m later` |
| exit ≥ 3 m earlier than the reference | `back on the throttle 9 m earlier` (throttle exits) / `hold the brake 6 m longer` (brake exits) |
| reference trails the brake ≥ 5 m further than the driver | `hold the brake 6 m past the apex` |

When nothing applies, the priority says so instead of inventing a cause:
`losing 0.4 s here with no single measurable cause — watch this corner on the
data`.

Sign convention, verified against the real session: `entry_distance_delta_m`
and `exit_distance_delta_m` are both `reference - driver`, so **positive means
the driver's phase happens earlier in the lap**. (The docstring on the exit
field said the opposite; that is corrected in this slice.)

## Test plan

1. Synthetic laps: a corner slow every lap outranks a corner that is only
   erratic; a clean corner is dropped.
2. Deduplication: a corner that is both slow and erratic appears once.
3. Suggestions: exact strings for gear, minimum speed, entry, exit-throttle,
   exit-brake and trail-brake; the fallback when there is no measurable cause.
4. `share_of_gap` is computed against the mean clean-lap gap.
5. Real session: priorities exist, are ranked, the top one is a real recurring
   loss, every suggestion carries a number, and the payload includes them.
