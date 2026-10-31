# Learnings — Slice 13 (Monza Curva Grande Circuit)

- **"Monza Curva Grande Circuit" is full Monza minus the Rettifilo chicane, not
  a short layout.** Lap distance 5742 m vs 5790 m for the full circuit — only
  48 m shorter. The name refers to Curva Grande now being taken flat (287 kph,
  6th gear, throttle 1.00) because there is no chicane to brake for. Two
  independent checks agree: the speed trace's first minimum is at ~2110 m
  (Roggia), with nothing at ~965 m where the full-Monza chicane lives; and the
  new outline tracks the TUMFTM Monza centreline within 5 m everywhere except
  exactly those five samples at ~970 m.

- **The turn count cross-checks the layout reading.** LMU/RaceCenter list this
  layout as 10 turns and full Monza as 11. Full Monza = Rettifilo ×2 + Curva
  Grande + Roggia ×2 + Lesmo ×2 + Ascari ×3 + Parabolica. Remove the two
  Rettifilo turns and add the Serraglio (an official Monza curve that the
  F1-style 11-turn numbering omits) and you get exactly the 10. That is how the
  Serraglio earned a slot in the model rather than being dismissed as noise.

- **`steering_norm` is useless for flat corners; position curvature is not.**
  Curva Grande shows max |steering| 0.085 and the Serraglio 0.028 — below any
  sane threshold, which is precisely why the throttle/brake detector sees 5
  corners and the track has 10. A three-point circle on the smoothed
  `pos_x_m`/`pos_z_m` trace found them cleanly (Curva Grande r≈317 m,
  Serraglio r≈1050 m) and matched the official published radii (≈300 m,
  >600 m) closely enough to trust the apex distance to a few metres.

- **The two sign conventions disagree, and both are documented wrong for each
  other.** On this lap curvature is **negative for right-handers** while
  `steering_norm` is **positive for right-handers**. Calibrate per lap against
  two known corners (I used Lesmo 1 = right and Roggia 1 = left) before setting
  any `apex_side`; do not carry a convention over from another track (the
  Laguna/Daytona note in slice 34 handoff says the same about steering).

- **Averaging curvature over a wider chord moves the apex by metres.** On Curva
  Grande the min-radius point wandered 1399 → 1412 → 1435 m as the chord grew
  0.5 s → 1 s → 1.5 s. For long, shallow curves pick one chord length, then
  cross-check against the steering peak (1335–1350 m here) before committing.
  For the flat corners I used the 0.5 s chord (apex 1400 m).

- **`register_outline.py` cannot rebuild the bundle on Windows.** It gets
  through validation, module generation and manifest edits, then dies in
  `subprocess.run` with `FileNotFoundError: [WinError 2]`. Everything except
  `product/dist/compare.html` is already written at that point, so the fix is
  just `npm run build`. Do not re-run the registrar afterwards — it is
  idempotent for the manifest, but you would hit the same crash again.

- **`test_track_outline_*` needs a working `python3`.** On this machine
  `python3` is the Microsoft Store stub, so `test_track_outline_recorder_channels.js`
  fails with "Python was not found". Copying `python.exe` to a temp dir as
  `python3.exe` and prepending it to `PATH` (plus `PYTHONIOENCODING=utf-8`)
  turns it green. The remaining `ERR_UNSUPPORTED_ESM_URL_SCHEME` failures
  (`test_track_outline_schema_compat.js`, `test_static_outline_runtime_rendering.js`)
  are the pre-existing Windows ESM problem: they do
  `await import(path.join(ROOT, ...))`, which passes `C:\...` to the loader.
  Neither is caused by adding a track.

- **`resolve_reference_lap(track, search_dir)` takes the directory as the
  second positional argument**, not the vehicle name. Passing the vehicle name
  positionally gives `'str' object has no attribute 'glob'` — use
  `vehicle_name=` explicitly.

- **Naming: check the official circuit first, not the F1 turn numbering.** The
  F1-style list ("T1…T11") has no Serraglio and calls the last corner
  Parabolica; the circuit's own site (monzanet.it) lists Curva Biassono (Curva
  Grande), Curva della Roggia, Lesmo 1/2, Curva del Serraglio, Variante Ascari
  and Curva Alboreto (Parabolica, renamed 2021). Both were used where they
  differ, since drivers, commentators and the sim UI all mix them.
