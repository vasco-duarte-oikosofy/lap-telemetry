# Learnings — Slice 34 (Daytona)

- **Steering sign convention is not portable across reference laps.** In the
  Laguna Seca reference, positive steering corresponded to a left-hand corner
  (Andretti Hairpin); in the Daytona reference the same convention would flip
  the International Horseshoe to "left" (it is a right-hand hairpin). The
  `pos_x`/`pos_z` heading-change method and the raw steering column gave
  contradictory results until cross-checked against the LMU guide. Conclusion:
  trust the track layout guide, not the steering sign, for apex sides.

- **Daytona is a "roval"** — ~half the lap is flat-out on the oval banking
  (back stretch 2200–3600 m, front stretch 4000–5732 m). The infield is only
  ~2.2 km of a 5.73 km lap, yet contains 6 of the 8 detected/manual corners.

- **The throttle-brake detector misses fast kinks.** Turn 2 and Turn 4 at
  Daytona are flat-out (no braking event, ~2–3 kph drop), so they were not
  detected. They had to be added manually from the steering trace (~700 m and
  ~1475 m).

- **The fastest race lap is not always the exportable reference.** Lap 9
  (1:44.521) was rejected by the authoritative-duration guard (frame-count
  mismatch) as a cut/abandoned lap; lap 11 (1:45.596) was the fastest clean one.
  This matches the documented behavior — don't be surprised when a fast summary
  line disappears at export time.

- **Test-suite environment issues on Windows:** `python3` is the Microsoft Store
  stub (not installed) so every Python-invoking test fails with "Python was not
  found" (9009); use `python`. Some Node ESM tests fail with
  `ERR_UNSUPPORTED_ESM_URL_SCHEME` on Windows paths. Neither is caused by adding
  track data.

- **Multi-session Daytona**: there are 4 Daytona sessions (2 practice, 1 quali,
  1 race). The user wanted the race session; the export script must be pointed
  at the race file (it superseded a practice-based reference automatically
  because the race lap was faster).
