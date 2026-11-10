# Learnings — Slice 05: improvement priorities

- **A suggestion must match the phase that is losing the time.** The first
  version produced clauses in a fixed order, so Pont — which loses 0.57 s on
  `exit_brake` — was told to "carry 2 km/h more minimum speed". The clause order
  is now chosen by the headline phase, and two clauses that open with the same
  words ("hold the brake 7 m longer" / "hold the brake 9 m past the apex") are
  collapsed into one.
- **Phase values have to be aggregated across laps, not taken from the first
  one.** Using the first phase fact produced "carry 20 km/h more minimum speed"
  at Signes where the real deficit is 2 km/h. Means for values, medians for
  distances, mode for gear.
- **Implausible distance deltas are detection noise, not advice.** Village
  produced "brake 178 m later". Anything past 60 m is now ignored: a driver who
  genuinely could brake 178 m later would already be doing it.
- **"Exited later" is not "exited early".** `exit_distance_delta_m` is
  `reference - driver`, so positive means the driver's phase happens *earlier*.
  Pont exits 11.5 m later than the reference, which correctly produces no timing
  clause — the loss there is exit speed, so the advice is "carry 7 km/h more
  speed onto the straight". The docstring on the field in `coach/facts.py` said
  the opposite; it is corrected in this slice.
- **Two speed clauses are one instruction.** `minimum_speed` and `exit` measure
  the same deficit through different windows; saying both reads as two separate
  problems.
- **The kind must be earned.** "Recurring" requires a real mean *and* at least
  60% of the laps where it was measurable. la Tour is "inconsistent" because the
  minimum-speed loss shows up on 6 of 9 laps, not all of them.
- **Ranking stays in seconds.** `score = recurring + 0.35 × spread` puts the
  corner that costs 0.70 s every lap (corner 2 at Paul Ricard) above the corner
  that swings 1.51 s but averages 0.29 s (Bretelle). That is the right coaching
  order: fix the guaranteed money first.
