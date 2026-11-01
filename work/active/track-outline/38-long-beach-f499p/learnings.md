# Learnings — Slice 38

- The session's fastest displayed lap is not a completed lap. Lap 4 looks like
  1:15.735 in summary but contains a garage teleport and reaches only 1.2 km.
  Guarded contiguous-segment selection correctly chooses lap 10 at 1:15.889.
- Long Beach has 11 official numbered turns but only eight detected braking
  events. Missing are flat T3 and T7, plus T10 hidden inside the final combined
  T10/T11 event. Renumbering the eight events would mislabel half the track.
- Steering sign is not an official side label until calibrated. Here negative
  is left (T1), positive right (T8/T11). The two flat left turns have sustained
  100% throttle/no brake over 50 m and 80 m spans, not just one point.
- The organiser's public circuit-map page serves a 2027 event poster today.
  Its numbered route matches the recorded layout; sponsor/hospitality labels
  are year-dependent, so stable Turn 1–Turn 11 names are the source of truth.
- The general outline baker regards all Turn N names as placeholders and would
  skip this model. This slice explicitly verifies the official 11-turn sequence
  and invokes the existing anchor baker on that reviewed list. Map aliases are
  null so the UI displays T10 instead of the spoken Ten alias.
- register_outline.py successfully writes the module/manifest but its Python
  subprocess cannot launch npm directly on Windows. The documented fallback
  npm run build succeeds; the registration backup was restored to its original
  state rather than committing incidental backup churn.
- Browser DOM has an outer #static-track-outline container and a nested
  [data-static-track-outline] group. Check the nested group for its track name;
  checking the outer container falsely reports a missing outline.
- Future updates remain vulnerable to shared bug 29: flat T3 is within 150 m
  of T4's braking apex. Tests pin flat geometry; a generic refresh must not be
  allowed to move it onto that neighbour. No shared matcher refactor was bundled.
