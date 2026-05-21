# Learnings — 01c.4 Losses and Gains Algorithm Review

## Delta-time formula works symmetrically for losses and gains

The same `delta_t[end] - delta_t[start]` formula naturally produces the
correct sign for both losses and gains. No branching needed.

## Losses change significantly with real delta-time

Turn 3 losses with the heuristic vs real delta-time:

| Phase | Heuristic | Real delta-time | Change |
|-------|-----------|-----------------|--------|
| exit_brake | 0.120s | 0.194s | +62% |
| minimum_speed | 0.106s | 0.190s | +79% |
| exit_throttle | 0.126s | 0.179s | +42% |

## Exit distance delta sign: positive = driver exited earlier (good)

Convention: `exit_distance_delta_m = ref_exit - driver_exit`.
- Driver at 2158, reference at 2168 → delta = +10 → driver was earlier (better exit).
- Driver at 1169, reference at 1165 → delta = -4 → driver was later (worse exit).

Entry is the reverse: positive = driver lifted earlier (more cautious).

## Phase matching: driver split ↔ reference merged

When the driver has split exit phases (`exit_brake` + `exit_throttle`)
but the reference has a merged `exit`, we match to the reference's
`exit`. This gives a single reference_phase_distance_m that both
driver phases compare against.

## Reference pedal data is available in Barcelona reference lap

The reference Parquet has `throttle_norm` and `brake_norm`. The JS
pipeline now resamples these alongside the driver pedal traces.

## Same-corner overlap is the prompt layer's problem

When min_speed and exit phases overlap for the same corner, the data
layer reports both honestly. Deduplication is the LLM prompt's
responsibility. Documented in the spec.