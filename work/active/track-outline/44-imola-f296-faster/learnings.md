# Learnings — Slice 44 (a faster lap is not automatically a better model)

- **The geometry-delta guard earned its keep immediately.** The first attempt
  aborted on Tamburello's exit moving 64 m (710 → 774), and it aborted *before*
  exporting anything. Without it, the faster reference and a wrong zone would
  have been written in the same step.

- **Some `s_end_m` values are driver behaviour, not geometry.** Tamburello's
  exit is the point where throttle re-crosses 0.90 — across six laps of one
  session it landed at 717/790/789/759/716/774 m. A model refreshed from a single
  lap records that lap's partial-throttle habit. The cure is `--preserve-geometry
  t1`, justified with the per-lap table, not a bigger threshold. Rule of thumb:
  before accepting a large delta, check how stable that boundary is **across
  laps**, not just whether it exceeds the guard.

- **Entry boundaries are noisy for the same reason.** Tamburello's entry swung
  503–549 m across the two sessions (braking point on a long straight depends on
  tow and traffic). Apex is the stable quantity; treat entry/exit with suspicion
  on corners fed by a straight.

- **`--preserve-geometry` is not only for flat/compound corners.** The docs
  frame it that way, but its actual contract is "reviewed zone must not claim an
  event". An unstable boundary is exactly that case. Both uses belong in the
  handoff so the next agent doesn't "fix" the preserved corner later.

- **Cross-session `--print-facts` is the strongest end-to-end proof.** Using the
  *previous* reference lap as the current lap reported exactly 0.639 s (the delta
  between the two references) with official corner names — that single number
  simultaneously validates the new reference's duration, the model's reference
  pointer and the corner IDs.

- **The outline question has a stable answer for new-car slices.** Outlines are
  per-layout and baked from the model the baker selects (ties → filename). A
  per-car refresh can never move it unless that car's model becomes the selected
  one — so "did the outline change?" is answered by a hash, not by re-baking.
