# Bug 27 — learnings

- **The reference/model resolvers were car-blind by design.** Both
  `reference_resolver.py` and `track_model_resolver.py` matched on track slug
  only and disambiguated multiple cars by "fastest" / "first". For tracks with
  more than one car (Lusail, Fuji, Daytona, Laguna Seca, Bahrain, …) the live
  coach silently picked another car's data. This is the same family of bug as
  bug 25 (layout variants) — both stem from "match by track, ignore the rest".

- **The fix's key idea: canonical car grouping via `vehicle_catalog.json`.**
  The repo already had a catalog mapping LMU `vehicle_name` →
  `{brand, model, slug}`. All Ferrari 296 GT3 liveries share
  `slug: ferrari-296-gt3`. The new `car_catalog.py` builds a reverse map
  (filename car-id slug → canonical slug) using the **same `vehicle_slug` rule
  as the export script** (`#` deleted, `:/` → `-`, whitespace → `-`). This is
  critical: the resolvers' `_track_slug` deletes `#:` and would NOT round-trip
  filename car-ids (`vista-af-corse-2026-54wec` vs the real
  `vista-af-corse-2026-54-wec`).

- **Catalog had a real-world gap.** It listed `"Vista AF Corsa 2026 #54:WEC"`
  (a typo) but the actual Lusail sessions use `"Vista AF Corse 2026 #54:WEC"`
  (both spellings occur across different sessions — Fuji Classic uses
  "Corsa"). Added the correct spelling plus the missing
  `"AF Corse 2025 #51:ELMS"`. **Lesson: when a session's utterances look
  bogus, first check whether the vehicle actually canonicalizes.**

- **Empty string ≠ None for `vehicle_name`.** `LapCompleted.vehicle_name`
  defaults to `""`. The car-filter gate must treat falsy/empty as "no vehicle
  given" (legacy behaviour), else it drops every car-specific file and
  coaching silently stops. Use `if not vehicle_name:` not `if vehicle_name is None:`.

- **Cache key had to include the vehicle.** Keying the resolver path-cache by
  track slug alone is fine for one car per session, but the key format changed
  to `f"{slug}|{vehicle_name or ''}"`. Existing tests that inspected the cache
  key (`test_live_after_lap_spoken_summary` T3b/T7b) had to be updated.

- **Per-session model caching already existed in the corner-exit generator**
  (`self._loaded_models`) but not in `LiveFactGenerator`, which re-parsed the
  JSON every lap. Added the same `_cached_model` helper keyed by resolved
  path. The reference Parquet is still re-read per lap (not changed — out of
  scope; the explicit ask was the coaching model).

- **Test environment gotchas on Windows:** the parallel runner's `.js`
  wrappers call `python`/`python3`, which hit the Microsoft Store stub
  (exit 9009) unless the venv is on PATH; and tests that print unicode (`→`)
  crash under cp1252 unless `PYTHONUTF8=1`. Run the suite with
  `PATH=".venv/Scripts:$PATH" PYTHONUTF8=1 bash scripts/test-summary.sh ...`.
  Several unrelated JS tests (apex_metrics, outline rendering) fail with
  `ERR_UNSUPPORTED_ESM_URL_SCHEME` on Windows — pre-existing, not from this
  change.