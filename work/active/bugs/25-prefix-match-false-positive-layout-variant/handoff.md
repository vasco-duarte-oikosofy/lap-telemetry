# Bug 25 handoff

## What changed

### Bug 25 original fix (prefix matching)
- `product/python/lap_telemetry/coach/track_model_resolver.py` — removed prefix matching, exact-match only
- `product/python/lap_telemetry/coach/reference_resolver.py` — same

### Accent transliteration fix (discovered while validating bug 25)
- `product/python/lap_telemetry/coach/track_model_resolver.py` — `_track_slug()` now transliterates via NFKD (ó→o, é→e) instead of stripping
- `product/python/lap_telemetry/coach/reference_resolver.py` — same
- `product/python/lap_telemetry/recorder/writer.py` — same
- `product/web/js/trackOutlineManifest.js` — JS slugify() now transliterates via NFKD; added `autodromo-jose-carlos-pace` key, kept `autdromo-jos-carlos-pace` as legacy fallback
- `product/data/reference-laps/autdromo-jos-carlos-pace_*` → renamed to `autodromo-jose-carlos-pace_*`

### Tests
- `dev/scripts/test_bug25.py` — added T6: accent transliteration tests
- `dev/scripts/test_live_after_lap_spoken_summary.py` — updated track names for exact matching

## What is on disk

- Both resolvers use exact slug matching + NFKD transliteration
- All 3 Python `_track_slug()` copies produce identical output
- JS slugify matches Python behavior
- All sessions in sessions/ resolve correctly
- Only Fuji Speedway Classic has no data (correctly suppressed)
- `npm run build` succeeds

## Deferred TODOs

- Existing session files in `sessions/` still have the old `autdromo-jos-carlos-pace` slug in their filenames. These are historical artifacts and don't need renaming — the track name comes from the JSON sidecar, not the filename.