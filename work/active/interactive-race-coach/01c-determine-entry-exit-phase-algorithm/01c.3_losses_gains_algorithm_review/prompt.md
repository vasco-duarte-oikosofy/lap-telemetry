# Slice 01c.3: Losses and Gains Algorithm Review

## Context

Slice 01c introduced algorithm-driven entry/exit phase detection (throttle lift, brake release, full throttle). Slice 01c.2 defines gain improvements: delta-time traces for measuring real time gained from a phase point to the end of the straight, and distance deltas (apex offset, entry delta, exit delta) comparing driver vs reference phase transitions.

Gains now use real integrated time: `loss_s = delta_t[straight_end] - delta_t[phase_point]`, negative for gains. But **losses still use the heuristic** `loss_s = speed_delta / 100.0`.

## Need

We must evaluate how to calculate **losses** so that we properly account for the full lap picture — both the gain algorithm and the loss algorithm working together consistently. Specific questions:

1. **Should losses also use delta-time?** A loss at the apex means the driver was slower. The time cost of that loss doesn't stop at the apex — it compounds down the straight (just like a gain). If we measure `loss_s = delta_t[straight_end] - delta_t[apex]` for losses the same way we do for gains, the semantics become consistent: every phase is measured in real seconds, and the sum across all phases should approximate the total lap time delta.

2. **Double-counting across phases.** If we measure the time from each phase point to the end of the straight, adjacent corners will overlap — the straight from corner N's apex to corner N+1's entry is counted in both corner N's measurement and corner N+1's entry. We need to decide whether phases should partition the lap (no overlap, no gaps) or whether overlap is acceptable for coaching purposes.

3. **Heuristic vs. real time mixing.** Currently minimum-speed gains use real seconds while minimum-speed losses use heuristic "seconds," and entry/exit phases use the heuristic in both directions. The ranking across phases (`corner_losses.sort(key=lambda x: x.loss_s)`) mixes units. Is this tolerable, or should we unify before shipping?

4. **Losses that don't compound to the end of the straight.** Some losses are "paid" entirely within the corner (e.g., late apex where the driver is slower through the corner but catches up on exit). A naive delta-time measurement from apex to end of straight would show a small loss or even a gain, even though the driver was slower at the apex. We need to decide whether to measure the loss at the point (speed delta) or over the segment (delta-time).

5. **Whole-lap accounting.** The sum of all phase `loss_s` values should approximate the total `lap_time_delta_s` for the lap. Currently it doesn't (heuristic `speed_delta / 100.0` has no relationship to real time). If we move to delta-time for all phases, the sum should converge — but we need to verify this with real data and address the overlap issue.

## Deliverable

A decision document specifying:
- Which `loss_s` formula to use for each phase (heuristic, delta-time, or hybrid).
- How to handle overlap between adjacent phases.
- Whether to unify the units before shipping or tolerate mixed units as a stepping stone.
- Any changes to the `CornerLoss` schema needed for consistency.

This is a **review and decision** slice, not an implementation slice. The output is a spec that the subsequent implementation slices will follow.