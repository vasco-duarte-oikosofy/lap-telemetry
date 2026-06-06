# Bug 25 handoff

## What changed

- `product/python/lap_telemetry/coach/track_model_resolver.py` — removed prefix matching (`slug.startswith(track_part + "-")`), now exact-match only
- `product/python/lap_telemetry/coach/reference_resolver.py` — same fix
- `dev/scripts/test_live_after_lap_spoken_summary.py` — updated test track names to use exact-match names
- `dev/scripts/test_bug25.py` + `dev/scripts/test_bug25.js` — new regression test for the bug

## What is on disk

- Both resolvers now use exact slug matching only
- All existing tests pass (the 20 failures are pre-existing Windows bugs — bug 20)
- `npm run build` succeeds

## Deferred TODOs

- If a future LMU track name (e.g., "Circuit de Barcelona-Catalunya") has a slug
  that doesn't exactly match the data file slug, coaching will be suppressed until
  the data file is renamed to match. This is the correct behavior — it's better to
  suppress coaching than to apply wrong-layout data.
- Could add a metadata-based matching strategy later (read JSON `track_id`/`layout_id`
  fields), but YAGNI until a real LMU track needs it.