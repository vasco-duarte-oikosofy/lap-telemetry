# Learnings — Slice 36 (Michelin Raceway Road Atlanta)

- **Road Atlanta officially has 12 turns, but Turn 4 is the whole Esses
  complex** (left-right-left, sometimes labelled 4a/4b/4c). The driver's guides
  disagree on whether "The Esses" is a separate item between T4 and T5
  (Driver61 map) or *is* T4 (Paddock Pal / Don Stevens). We used the Paddock
  Pal reading: one `t4` entry covering 880–1300 m, apex at the 4b right.
  If a later reviewer wants the sub-apeses on the map, split into t4a/t4b/t4c.

- **The detector's 7 corners were not the official turns.** It found
  T1, T2+T3 (merged, brake never fully released between them), T5, T6, T7,
  10A and 10B. The flat-out turns — T4 (Esses), T8, T9, T11, T12 — produce no
  brake event and were added manually from the speed/steering trace:
  - T8 is a gentle left around 2470 m, T9 a gentle right around 3100 m on the
    1 km back straight.
  - T11 is the blind right kink under the bridge (~3710 m).
  - T12 is the fast downhill right onto the front straight (~3990 m).
  All four are flat-out at 100 % throttle in the LMP3 (throttle stays 1.00).

- **T4 is mostly flat but not perfectly so.** Throttle dips to ~0.61 around
  1110 m (the 4b right) — a small correction, no brake. T10B is similar
  (throttle lift to ~0.45, no brake), so it was left as a normal zone with no
  `target_throttle_pct` pin. Only truly flat corners get `target_throttle_pct:
  100`.

- **Steering sign is portable on this lap** (+ = right), unlike Laguna (slice
  35). Verified against T1 (right), T7 (right), T10A (left), T10B (right).
  Apex sides here are from the steering trace and the track guide.

- **"Outline not showing" was the filename parser, not the outline.** The
  manifest lookup worked (`findOutlineByTrackName('Michelin Raceway Road
  Atlanta')` returned the outline), which made the data look correct. But the
  app never got that far: it derived the track name from the file name only
  when no sidecar was loaded, and the regex only matched the legacy
  `_lmu.parquet` form. Lesson: test the *whole* load path in the app
  (Playwright + outline-pixel probe), not just the manifest lookup, before
  declaring an outline done.

- **The reference time was wrong in two places for the same reason.** Both the
  web app (`annotateSegments` fallback) and the model generator used
  `max(lap_time_s)`, which undercounts the real lap by ~0.6 s. The authoritative
  value lives in the `_time_MM.SS.mmm.parquet` filename. Any new consumer of
  reference-lap duration must parse the filename (or carry the value), not read
  `lap_time_s`.

- **Windows test environment**: `python3` is the Microsoft Store stub. A real
  `python3` is required for the Python test wrappers. Fix on this machine:
  copy `python.exe` → a temp `python3.exe` and prepend it to PATH, plus set
  `PYTHONIOENCODING=utf-8` (the wrappers crash on `✅` inside cp1252). With
  both fixes the suite is 1226 passed / 6 failed, all pre-existing Windows
  `ERR_UNSUPPORTED_ESM_URL_SCHEME` harness failures.

- **New tests must be added to `scripts.test` in package.json.** The suite is
  an explicit `&&`-chain, not auto-discovered; a new `dev/scripts/test_*.js`
  simply never runs until it is appended there.
