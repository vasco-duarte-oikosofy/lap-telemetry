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

- **The reference time was wrong, then "fixed" the wrong way, then fixed
  properly.** The web app and generator both used `max(lap_time_s)` (~0.1 s
  short) and `scoring_last_lap_time_s` (mLastLapTime, which lags a lap on
  Road Atlanta: 77.345 = lap 14). The in-game truth (confirmed against
  TinyPedal's deltabest, 76.80896) is the **telemetry lap-start ET
  difference** between consecutive laps — `lmuTeleVeh.mLapStartET`, which our
  recorder stores implicitly as `session_time_s - lap_time_s`. Lesson: the
  scorer's mLastLapTime is not authoritative; prefer the telemetry clock.
  See `work/active/bugs/28-lap-duration-telemetry-clock/`.

- **Windows test environment**: `python3` is the Microsoft Store stub. A real
  `python3` is required for the Python test wrappers. Fix on this machine:
  copy `python.exe` → a temp `python3.exe` and prepend it to PATH, plus set
  `PYTHONIOENCODING=utf-8` (the wrappers crash on `✅` inside cp1252). With
  both fixes the suite is 1235 passed / 6 failed, all pre-existing Windows
  `ERR_UNSUPPORTED_ESM_URL_SCHEME` harness failures.

- **The updater used to strip `target_throttle_pct` from matched corners.**
  `refresh_corners()` (in `update_reference_and_coaching_model.py`) rebuilt
  each matched corner from a fixed key list, so any curated field not in that
  list — the flat-turn `target_throttle_pct: 100` marker — was silently lost.
  Fixed to copy the existing corner dict and overwrite only the geometry.
  This matters because a flat turn can accidentally be "matched" by a nearby
  braking candidate (e.g. T11 by the T10B exit). Test:
  `dev/scripts/test_update_coaching_model.{py,js}`.

- **T4 is still not taken fully flat on the new fastest lap.** The race lap
  15 telemetry shows throttle min ≈ 0.50 and a light brake peak ≈ 0.17 through
  the Esses (880–1300 m). So it remains exactly the old case: a mostly-flat
  complex with a small 4b correction, kept as a real zone with
  `target_throttle_pct: 100`. The detector still emits no candidate there, so
  the updater must keep it via `--allow-unmatched` — which is why the
  corner-preservation fix above matters.

- **A suspicious sub-median lap time is a restart artifact, not a fast lap.**
  Session `155735` lists lap 22 at 1:15.994 with no sector times (lap 23 is
  missing). The export guards reject it (wall-clock span vs authoritative time
  / full-lap coverage), so the real fastest remains race lap 15 at 1:16.304.
  Trust the guards over the raw summary table.

- **New tests must be added to `scripts.test` in package.json.** The suite is
  an explicit `&&`-chain, not auto-discovered; a new `dev/scripts/test_*.js`
  simply never runs until it is appended there. Add it to the relevant
  `testFeatures` list too (model tests → `interactive-race-coach`).
