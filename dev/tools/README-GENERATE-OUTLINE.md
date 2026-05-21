# Generate Track Outline from Trajectory Data

This guide explains how to generate a track outline JSON file from a single reference lap.

## Overview

Use the **single reference lap** for every new circuit — pass it twice to satisfy the
script's 2-lap minimum. Median of two identical laps is the lap itself, so the outline
is an exact trace of the reference lap with ±5 m boundaries.

Do **not** average multiple laps. Point-by-point averaging across different racing lines
produces jitter in corners. One clean lap gives a smooth, accurate outline.

---

## Procedure

### 1. Extract the reference lap (if not already done)

The reference lap must already exist in `product/data/reference-laps/`. If it doesn't,
follow `dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md` first.

### 2. Generate the outline

Pass the reference lap parquet **twice** (the script requires ≥2 laps; the median of
two identical inputs is the input itself):

```bash
PYTHONIOENCODING=utf-8 python dev/scripts/average_trajectory_outline.py \
  product/data/track-outlines/<track-slug>.json \
  --sessions \
    product/data/reference-laps/<ref-lap>.parquet \
    product/data/reference-laps/<ref-lap>.parquet
```

Example for COTA:

```bash
PYTHONIOENCODING=utf-8 python dev/scripts/average_trajectory_outline.py \
  product/data/track-outlines/circuit-of-the-americas.json \
  --sessions \
    product/data/reference-laps/circuit-of-the-americas_dkr-engineering-4-elms25_time_02.04.130.parquet \
    product/data/reference-laps/circuit-of-the-americas_dkr-engineering-4-elms25_time_02.04.130.parquet
```

### 3. Fix the track name in the output JSON

The script cannot read the track name from the parquet metadata, so it writes
`"Unknown"`. Patch it before registering:

```python
PYTHONIOENCODING=utf-8 python -c "
import json
with open('product/data/track-outlines/<track-slug>.json') as f:
    o = json.load(f)
o['track_name'] = '<Human-readable track name>'
o['sim_track_name'] = '<Human-readable track name>'
o['track_name_mapping'] = {
    'canonical_sim_track_name': '<track-slug>',
    'canonical_lmu_track_name': '<Human-readable track name>',
    'accepted_sim_track_names': ['<track-slug>'],
    'accepted_lmu_track_names': ['<Human-readable track name>'],
    'notes': 'Generated from single reference lap (<ref-lap-filename>).'
}
with open('product/data/track-outlines/<track-slug>.json', 'w') as f:
    json.dump(o, f, indent=2)
"
```

The `canonical_sim_track_name` / `accepted_sim_track_names` must match the slugified
form of the `track` field in the session sidecar JSON (e.g. `"Circuit of the Americas"`
→ `"circuit-of-the-americas"`).

### 4. Register and rebuild

```bash
PYTHONIOENCODING=utf-8 python dev/scripts/register_outline.py \
  product/data/track-outlines/<track-slug>.json

npm run build
```

`register_outline.py` is **idempotent** — safe to run twice. It:
1. Validates the outline JSON
2. Generates the ES module (`product/web/js/static<Track>OutlineData.js`)
3. Adds the import and OUTLINES map entry to `product/web/js/trackOutlineManifest.js`
4. Rebuilds `product/dist/compare.html`

> **Note:** `register_outline.py` calls `npm run build` internally but may fail with a
> `FileNotFoundError` on Windows. If that happens, run `npm run build` manually — the
> registration itself will already have succeeded.

### 5. Verify

Open `product/dist/compare.html` in the browser, load a session for the new circuit,
and confirm the circuit map appears in the sidebar.

---

## Example: Circuit of the Americas

```bash
# 1. Generate
PYTHONIOENCODING=utf-8 python dev/scripts/average_trajectory_outline.py \
  product/data/track-outlines/circuit-of-the-americas.json \
  --sessions \
    product/data/reference-laps/circuit-of-the-americas_dkr-engineering-4-elms25_time_02.04.130.parquet \
    product/data/reference-laps/circuit-of-the-americas_dkr-engineering-4-elms25_time_02.04.130.parquet

# 2. Patch track name (see step 3 above)

# 3. Register + rebuild
PYTHONIOENCODING=utf-8 python dev/scripts/register_outline.py \
  product/data/track-outlines/circuit-of-the-americas.json
npm run build
```

---

## See Also

- `dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md` — how to extract and store the reference lap
- `dev/tools/manual_outline_align.html` — visual QA tool
- `product/web/js/trackOutlineManifest.js` — OUTLINES map
