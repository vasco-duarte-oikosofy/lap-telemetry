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
used in data files. The logic is (line 89 of `track_model_resolver.py`, line 88
of `reference_resolver.py`):

```python
if track_part == slug or slug.startswith(track_part + "-"):
    matching.append(p)
```

This correctly handles cases like:
- `"Circuit de Barcelona-Catalunya"` → slug `circuit-de-barcelona-catalunya` →
  matches `circuit-de-barcelona` (the model file's prefix)

But it **incorrectly** matches layout variants:
- `"Fuji Speedway Classic"` → slug `fuji-speedway-classic`
- Track part of model file: `fuji-speedway` (from file `fuji-speedway_dkr-engineering-4-elms25.json`)
- `"fuji-speedway-classic".startswith("fuji-speedway-")` → **`True`**

The resolver returns the fuji-speedway model as a match, even though "Classic" is
a **different circuit layout** (different corners, different lap length), not a
name variant of the same circuit.

The same false match occurs in `reference_resolver.py` for the reference lap file.

## Impact

1. **Wrong coaching model loaded**: The Fuji Speedway model (lap_length 4538.9 m,
   specific corner definitions) is applied to Fuji Speedway Classic (likely a
   different length with different corners). Corner detection and distance-based
   segmentation will be wrong.

2. **Wrong reference lap used**: The fuji-speedway reference lap is compared against
   Classic layout data, producing meaningless delta times and coaching advice.

3. **Silent misuse**: No warning or error — the user hears coaching as if it's
   authoritative, but the data is from a different layout.

## Proposed fix

The prefix-matching heuristic needs to distinguish between:

| Live slug               | File track_part           | Should match? | Why                          |
|--------------------------|---------------------------|---------------|------------------------------|
| `circuit-de-barcelona-catalunya` | `circuit-de-barcelona` | ✅ Yes        | Same layout, longer name     |
| `fuji-speedway-classic`  | `fuji-speedway`           | ❌ No          | Different layout (variant)   |
| `fuji-speedway`           | `fuji-speedway`           | ✅ Yes        | Exact match                  |

Options:

1. **Remove prefix matching entirely**: Only allow exact slug matches. This is the
   safest but requires renaming existing data files (e.g., `circuit-de-barcelona_*`
   → `circuit-de-barcelona-catalunya_*`) to match LMU's full track names.

2. **Add a blocklist of known layout suffixes**: Reject prefix matches where the
   extra suffix is a known layout word (`classic`, `endurance`, `short`, `oval`,
   `grand-prix`, `national`, etc.). Fragile — new layouts may be added.

3. **Match on the data file's own metadata instead of filename parsing**: Load each
   candidate JSON file's `track_id`/`layout_id` fields and compare to the live
   track name. For reference laps (Parquet), check the Parquet metadata or a
   companion sidecar file. This is robust but requires reading all candidates.

4. **Reverse the match direction**: Instead of checking `slug.startswith(track_part)`,
   check `track_part == slug OR (file has a metadata field confirming it covers
   the slug's layout)`. This avoids the false positive while preserving the
   Barcelona-Catalunya case.

**Recommended**: Option 3 (metadata-based matching) for `track_model_resolver.py`
since JSON files already contain `track_id` and `layout_id`. For
`reference_resolver.py`, add a companion sidecar or embedded Parquet metadata
check. As a quick interim fix, Option 1 (exact match only) is safest.

## Affected files

- `product/python/lap_telemetry/coach/track_model_resolver.py` (line 89)
- `product/python/lap_telemetry/coach/reference_resolver.py` (line 88)
- `product/python/lap_telemetry/coach/live_fact_generator.py` (calls both resolvers)
- `product/python/lap_telemetry/coach/live_corner_fact_generator.py` (calls both resolvers)

## Status

🐛 Open