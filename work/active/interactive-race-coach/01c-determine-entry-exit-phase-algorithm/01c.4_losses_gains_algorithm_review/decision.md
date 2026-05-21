# Decision: Losses and Gains Algorithm Review

## Decision 1: Extend delta-time to losses for all phases — YES

All three phases currently use `speed_delta / 100.0` for losses and
`delta_t[end] - delta_t[start]` for gains. The same delta-time formula
works for both directions because the sign is natural:

- Driver slower at phase point → `delta_t` positive (behind) →
  disadvantage compounds → segment delta is positive = **loss**.
- Driver faster at phase point → `delta_t` negative (ahead) →
  advantage compounds → segment delta is negative = **gain**.

### Unified formulas

| Phase       | Formula (both loss and gain)          | Window                    |
|-------------|--------------------------------------|---------------------------|
| entry       | `delta_t[apex] - delta_t[entry]`     | entry_point → apex        |
| minimum_speed | `delta_t[straight_end] - delta_t[apex]` | apex → straight_end    |
| exit        | `delta_t[straight_end] - delta_t[exit]` | exit_point → straight_end |

The `speed_delta / 100.0` heuristic is removed entirely. All `loss_s`
values are now in real seconds.

### Self-correcting losses

If a driver is slower at the apex but catches up by straight-end, the
delta-time loss will be small or even negative. This is **correct
coaching information**: "You were 12 kph slower at the apex but it only
cost you 0.03s." The speed data remains available in
`driver_value`/`reference_value` for point-in-time comparison.

### Code simplification

The `if speed_delta > 0: heuristic else: delta_time` branches are
eliminated in all three phases.

## Decision 2: Overlap between adjacent phases — ACCEPT as-is

When losses use delta-time, the same overlap issue exists as for gains:

- Corner N's exit/minimum_speed loss is measured to `straight_end`
  (= next corner's entry point).
- Corner N+1's entry loss is measured from entry to apex.

These two measurement windows share no distance — entry ends at apex,
exit/min-speed starts at apex or exit and goes to straight_end. So
there is **no overlap** when using the same phase boundaries already
established for gains.

The only apparent overlap is conceptual: the straight between corner N
and corner N+1 contributes to corner N's exit gain *and* corner N+1's
entry... but the windows don't overlap (corner N: exit_point →
straight_end; corner N+1: entry_point → apex). The straight segment
between exit and next-entry is counted in corner N's window; the
entry-to-apex segment is counted in corner N+1's window. No
double-counting within the same meters.

## Decision 3: `speed_delta / 100.0` — REMOVE entirely

No longer needed. All phases now use real delta-time. The heuristic was
a placeholder; removing it makes all `loss_s` values dimensionally
consistent (seconds) and enables whole-lap accounting validation.

## Decision 4: `entry_distance_delta_m` and `exit_distance_delta_m` — DEFER

These compare driver vs reference phase-transition distances ("you
lifted 8 m later than reference"). They are orthogonal to the delta-time
unification and add significant detection complexity (resample reference
pedal traces, detect reference entry/exit points). Defer to a future
slice.

## Decision 5: `gain_end_distance_m` for losses — POPULATE always

Currently `gain_end_distance_m` is only set for gains. After this change,
every phase has a measurement window with a defined end point, so
`gain_end_distance_m` should always be populated regardless of loss/gain
direction. The field name is slightly misleading for losses but
semantically it means "the distance where the measurement window ends."
A rename to `measurement_end_distance_m` is optional; the current name
is acceptable for now.

## Decision 6: Schema changes

No new fields needed on `CornerLoss`. The existing `gain_end_distance_m`
is simply populated for losses too. The `loss_s` field semantics change
from "heuristic for losses / real for gains" to "real delta-time for
both" — this is a compatible change (same sign convention, same
approximate magnitude).

## Decision 7: Whole-lap accounting validation

After this change, the sum of all positive `loss_s` values should
approximate `lap_time_delta_s` (the actual lap time difference). This
validation should be added to the test suite as a sanity check. It will
not be exact (phase boundaries, shared straights, self-correcting
losses) but should be within a reasonable tolerance.