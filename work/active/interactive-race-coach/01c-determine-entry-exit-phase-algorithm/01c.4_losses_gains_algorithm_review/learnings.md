# Learnings — 01c.4 Losses and Gains Algorithm Review

## Key insight: delta-time formula works symmetrically for losses and gains

The same `delta_t[end] - delta_t[start]` formula naturally produces the
correct sign for both losses and gains:
- Driver slower → delta_t is positive at the phase point → disadvantage
  typically compounds → segment delta is positive = loss.
- Driver faster → delta_t is negative → advantage compounds → negative = gain.

This eliminates the need for `if speed_delta > 0: heuristic else: delta_time`
branches entirely.

## Losses change significantly with real delta-time

Turn 3 losses with the heuristic vs real delta-time:

| Phase | Heuristic | Real delta-time | Change |
|-------|-----------|-----------------|--------|
| exit_brake | 0.120s | 0.194s | +62% |
| minimum_speed | 0.106s | 0.190s | +79% |
| exit_throttle | 0.126s | 0.179s | +42% |

The real values are substantially larger because they capture the
compounded time cost down the straight — the heuristic was significantly
under-reporting losses.

## Self-correcting losses did not appear in Barcelona data

The scenario where a driver is slower at a phase point but catches up
by the measurement end did not occur in the test fixture. This is
expected — if you're slower at the apex, you're almost always slower
down the entire straight. The speed data (driver_value/reference_value)
is still available to flag the rare case.

## gain_end_distance_m naming slightly misleading for losses

The field was originally named for gains only. Now it's populated for
both losses and gains. A rename to `measurement_end_distance_m` would
be clearer but is deferred — the current name works and renaming would
touch the web UI.

## No overlap between adjacent phases

Corner N's exit/min-speed window: exit_point → straight_end.
Corner N+1's entry window: entry_point → apex.
These share no distance — entry ends at apex, exit starts at exit_point
and goes to straight_end. No double-counting occurs.

## The heuristic fallback still exists

When delta_t indices are out of range, the code falls back to
`speed_delta / 100.0`. This should trigger very rarely (only for data
quality issues or track-length mismatches) but is kept as a safety net.