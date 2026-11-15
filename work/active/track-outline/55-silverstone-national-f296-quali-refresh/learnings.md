# Learnings — Slice 55

- Qualifying lap 1 appears valid and is only 40.009 s; that is not a faster
  National lap. Full-distance and row-count guards reject it. Use the complete
  segment candidate list rather than sorting the raw summary by time.
- Lap 10 is 54.106018 s by lap-start telemetry clocks, while its wall-clock span
  is 54.0 s and max(lap_time_s) is shorter. Export metadata correctly stores
  54.106; the filename and model use the same millisecond-rounded value.
- The new F296 Brooklands apex coincides with the P3 apex (1921 m). The old
  regression required every braked apex to differ from the P3, which is not a
  meaningful invariant. Pin the reviewed F296 entry/apex/exit triple instead.
- Both flat zones remain genuinely flat on this new lap (throttle 1.0, brake
  0.0 throughout). Preserving their full objects avoids losing reviewed geometry
  as well as the 100% targets; they must not claim neighbouring brake events.
- Copse's detected throttle-resumption boundary is only 1 m beyond its apex,
  down from 4 m. This is the previously documented detector behavior; no phase
  algorithm or hand-curated exit repair belongs in this reference refresh.
- On this checkout, direct `extract_reference_lap.py` needs
  `PYTHONPATH=product/python`; the exporter/updater add that path themselves.
  The initial extraction failed before writing; rerunning with the environment
  set produced the recorded successful lap-9 comparison.
- The outline intentionally follows the P3 model; refreshing F296 geometry does
  not require rebaking the shared map or touching the user's TinyPedal labels.
