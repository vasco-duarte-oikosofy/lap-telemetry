# Slice 01c.4: Losses and Gains Algorithm Review

## Context

Slice 01c introduced algorithm-driven entry/exit phase detection. Slice 01c.2 implemented delta-time gains for all three phases:

| Phase | Loss | Gain |
|-------|------|------|
| minimum_speed | `speed_delta / 100.0` (heuristic) | `delta_t[straight_end] - delta_t[apex]` (real time) ✅ |
| exit | `speed_delta / 100.0` (heuristic) | `delta_t[straight_end] - delta_t[exit_point]` (real time) ✅ |
| entry | `speed_delta / 100.0` (heuristic) | `delta_t[apex] - delta_t[entry_point]` (real time) ✅ |

All gains now use real delta-time. All losses still use the `speed_delta / 100.0` heuristic. This is the remaining asymmetry to resolve.

## Two items to address

### 1. Losses — review and confirm or change

Losses currently use `speed_delta / 100.0` for all phases. The questions:

- **Should losses also use delta-time?** A loss at the apex means the driver was slower. The time cost compounds down the straight (just like a gain). If we measure `loss_s = delta_t[straight_end] - delta_t[phase_point]` for losses too, the semantics become consistent: every phase is measured in real seconds.
- **Double-counting across phases.** The straight from corner N's apex to corner N+1's entry is counted in both corner N's measurement and corner N+1's entry. Is overlap acceptable for coaching purposes, or should phases partition the lap?
- **Losses that "self-correct."** A late apex where the driver is slower through the corner but catches up on exit would show a small delta-time loss (or even a gain) at the end of the straight, even though the driver was clearly slower at the apex. Speed delta measures the point-in-time difference; delta-time measures the segment difference. Which is more coaching-useful for losses?
- **Whole-lap accounting.** If all phases use delta-time, the sum of all `loss_s` values should approximate `lap_time_delta_s`. Does it? This needs verification with real data.

### 2. Distance deltas: entry and exit

Both entry and exit phases currently compare speeds but not *where* the phase transition happened. Coaching-meaningful facts like "you lifted 8 m later than reference" or "you got back to full throttle 12 m later" require detecting the reference lap's entry and exit points, which isn't currently implemented.

## Deliverable

A decision document specifying:
- Whether to extend delta-time to losses for all phases.
- How to handle overlap between adjacent phases (if losses use delta-time).
- Whether `speed_delta / 100.0` is acceptable for losses, or whether delta-time is required for consistency.
- Whether to implement `entry_distance_delta_m` and `exit_distance_delta_m` now.
- Any changes to the `CornerLoss` schema needed for consistency.

This is a **review and decision** slice, not an implementation slice.