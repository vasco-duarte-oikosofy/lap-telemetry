# Bug 27 — handoff

## State on disk

Fix committed (see commit hash in `bug.md` Status). The live coach now resolves
the reference lap **and** coaching model for the correct car, and loads the
coaching model once per session.

## Files changed

**New:**
- `product/python/lap_telemetry/coach/car_catalog.py` — vehicle catalog loader
  + `canonical_car_slug`, `car_id_canonical_slug`, `prioritize_for_car`.
- `dev/scripts/test_bug27.py` + `dev/scripts/test_bug27.js` — regression test
  (20 assertions).
- `work/active/bugs/27-car-blind-coaching-resolution/` — this bug folder.

**Modified:**
- `reference_resolver.py` — optional `vehicle_name`; car-aware filtering via
  `prioritize_for_car`; cache key now `f"{slug}|{vehicle_name or ''}"`.
- `track_model_resolver.py` — same; generic (no-car) model is a last-resort
  fallback (priority 2).
- `lap_detector.py` — `LapCompleted` / `NewLap` carry `vehicle_name`,
  populated from `Frame.vehicle_name`.
- `corner_exit_detector.py` — `CornerExited` carries `vehicle_name`.
- `coach_tap.py` — passes `event.vehicle_name` to `generate_from_parquet`.
- `live_fact_generator.py` — `generate_from_parquet` takes `vehicle_name`;
  both `generate*()` pass it to resolvers; coaching model cached per resolved
  path via `_cached_model` (loaded once per session).
- `live_corner_fact_generator.py` — passes `event.vehicle_name` to resolvers.
- `product/data/vehicle_catalog.json` — added `Vista AF Corse 2026 #54:WEC`
  (real Lusail spelling) and `AF Corse 2025 #51:ELMS`; kept the `Corsa` typo
  variant (real Fuji Classic sessions use it).
- `dev/scripts/test_live_after_lap_spoken_summary.py` — updated cache-key
  assertions (T3b/T7b) for the new `slug|vehicle` format; `_make_frame`
  default vehicle is now the real `DKR Engineering #4:ELMS25`.
- `package.json` — `test_bug27.js` added to `interactive-race-coach` feature.

## Behaviour

- `vehicle_name` given → candidates narrowed to the same canonical car
  (exact car-id first, then same canonical slug, then generic no-car model).
  No match → `None` (coaching skipped; never uses another car's data).
- `vehicle_name` absent/empty → legacy behaviour (fastest/first), unchanged.
- Coaching model JSON is parsed once per session and kept in memory; the
  reference Parquet is still read each lap (not cached — out of scope).

## Verification

- `bash scripts/test-summary.sh --feature interactive-race-coach` →
  **ALL PASS — 771 assertions across 24 scripts** (run with
  `PATH=".venv/Scripts:$PATH" PYTHONUTF8=1` on Windows).
- `test_bug27.py` reproduces the original bug verbatim: Ferrari lap 12 at
  Lusail now resolves to the Ferrari reference/model, not the LMP3.
- Pre-existing failures NOT caused by this change:
  - `test_bug25.py` T1/T2 — stale ("Fuji Speedway Classic returns None" but
    Fuji Classic data now exists). Bug 25's fix still works; only the test
    expectation is stale. Out of scope; left as-is.
  - 5 JS tests (`test_apex_metrics*`, `test_static_outline_runtime_rendering`,
    `test_apex_annotations`) fail with `ERR_UNSUPPORTED_ESM_URL_SCHEME` on
    Windows node — pre-existing, unrelated to Python coach code.

## Deferred TODOs

- Update `test_bug25.py` T1/T2 to expect the now-existing Fuji Classic data
  (separate cleanup).
- `dev/scripts/export_fastest_reference_laps.py` has its own `vehicle_slug`
  copy; could import from `car_catalog` to dedupe (refactor, not behaviour).
- Reference Parquet is re-read every lap; could be cached per session too
  (the user's explicit ask was the coaching model only).