# Bug 25 — Prefix-match false positive: coaching fires on tracks with no model

## Symptom

When driving **Fuji Speedway Classic** (a different layout from Fuji Speedway), the
coach still produces utterances as if a coaching model and reference lap exist for
that layout. The coaching model for **Fuji Speedway** (the main layout, 4538.9 m)
is incorrectly matched and applied to the Classic layout, which has a different
circuit configuration.

## Reproduction

1. Start the coach with a session at Fuji Speedway Classic:
   `session_20260606T131054Z_fuji-speedway-classic_lmu_practice`
2. Observe that coaching utterances are generated despite no coaching model or
   reference lap existing for `fuji-speedway-classic`.
3. The only files available are:
   - `product/data/track-coaching/fuji-speedway_dkr-engineering-4-elms25.json`
   - `product/data/reference-laps/fuji-speedway_dkr-engineering-4-elms25_time_01.38.135.parquet`
   - Neither is for the Classic layout.

## Root cause

Both `track_model_resolver.py` and `reference_resolver.py` use a **prefix-matching
heuristic** to handle track name variations between LMU's track name and the slug
used in data files. The logic was:

```python
if track_part == slug or slug.startswith(track_part + "-"):
    matching.append(p)
```

This correctly handled cases like `"Circuit de Barcelona-Catalunya"` matching
`circuit-de-barcelona` model files, but **incorrectly** matched layout variants:

- `"Fuji Speedway Classic"` → slug `fuji-speedway-classic`
- Track part of model file: `fuji-speedway`
- `"fuji-speedway-classic".startswith("fuji-speedway-")` → `True`

The resolver returned the fuji-speedway model as a match, even though "Classic" is
a **different circuit layout**, not a name variant.

## Fix

Removed prefix matching from both resolvers. Only exact slug matches are now
accepted. This is safe because every real LMU track name already has an exact
match in both data directories — the prefix matching was designed for a
hypothetical Barcelona-Catalunya case that doesn't exist in production.

Changes:
- `product/python/lap_telemetry/coach/track_model_resolver.py`: removed
  `slug.startswith(track_part + "-")` condition and the exact-vs-prefix
  disambiguation logic.
- `product/python/lap_telemetry/coach/reference_resolver.py`: same removal.
- `dev/scripts/test_live_after_lap_spoken_summary.py`: updated test track names
  from "Circuit de Barcelona-Catalunya" to "Circuit de Barcelona" (exact match).
- `dev/scripts/test_bug25.py` + `dev/scripts/test_bug25.js`: new regression test.

## Status

✅ Fixed