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

- **The recorder contract is directly testable.** For every completed lap in a
  recorded session, `session_time_s - lap_time_s` is constant to <0.00002 s
  (only lap 0, the out-lap, drifts because `mLapStartET` changes mid-segment).
  This gives a cheap, live-independent invariant that proves the telemetry
  clock is recoverable, and it is now asserted in
  `test_lap_duration_surfaces.py`.

- **The manual fallback path forgot to persist the duration.**
  `extract_reference_lap.py` computed the authoritative duration via the
  telemetry clock but wrote the parquet without the `authoritative_lap_time_s`
  metadata, so a manually extracted single-segment file was still ~0.1 s short
  downstream. It now stamps the same metadata as the guarded exporter.

- **Testing the built bundle needs `product/dist`, not `product/web`.** The
  other Playwright tests serve the source tree; `test_compare_reference_duration.js`
  serves `product/dist` and loads `/compare.html`, so it actually exercises the
  shipped single-file build. Playwright tests are auto-skipped unless `--pw`.
