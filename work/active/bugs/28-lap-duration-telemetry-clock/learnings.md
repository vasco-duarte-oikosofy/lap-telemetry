# Learnings — Bug 28 (lap duration telemetry clock)

- **The scorer is not the source of truth.** `mLastLapTime`
  (`scoring_last_lap_time_s`) can lag a full lap. On Road Atlanta lap 15 it
  held lap 14's time (77.345 vs the true 76.809). The bug hid because on Paul
  Ricard it matched exactly, which is why bug 13's scorer-first fix looked
  correct.

- **TinyPedal uses the telemetry lap-start clock.** `lap_stime =
  lmuTeleVeh.mLapStartET`; duration = consecutive start deltas. Our recorder
  already stores that implicitly as `session_time_s - lap_time_s`. This is a
  pure read-side fix — no re-recording needed.

- **Two "authoritative" values can both be wrong in opposite directions.**
  `max(lap_time_s)` shorts the last partial sample (~0.09 s); `mLastLapTime`
  can overshoot by ~0.5 s (a stale lap). "Pick the larger/smaller" heuristics
  are not enough; the correct clock must be identified.

- **A ground-truth cross-check saves a lot of guessing.** TinyPedal's
  `deltabest/Michelin Raceway Road Atlanta - LMP3.csv` ends at 76.80896,
  matching the telemetry computation to the millisecond — decisive.

- **The reference filename was a downstream symptom, not the cause.** The
  previous attempt (bug 36 follow-up) "fixed" the app/model to agree with the
  filename (1:17.345); the filename itself was produced by the wrong helper.
  Always fix the producer before the consumers.
