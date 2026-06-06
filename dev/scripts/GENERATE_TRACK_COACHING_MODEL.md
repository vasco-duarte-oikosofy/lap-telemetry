# Generating a Track Coaching Model

A **track coaching model** is a JSON file that describes every corner on a circuit: apex distance, entry/exit zones, minimum speed, and associated metadata. It is stored under `product/data/track-coaching/` and is consumed by `compare-laps` and the live coach.

## Naming convention

```
product/data/track-coaching/<track-slug>_<car-id>.json
product/data/track-coaching/<track-slug>_<car-id>.diagnostics.txt
```

- `<track-slug>`: circuit name as it appears in session filenames (e.g. `lusail-international-circuit`).
- `<car-id>`: car identifier (e.g. `dkr-engineering-4-elms25`).

One model per track+car combination. The script **overwrites** the output file, which destroys any curated content (real corner names, manual apex sides, manually added turns). Therefore (bug 24):

- **New track+car (no model yet):** use this script.
- **Track+car already has a model:** do NOT re-run this script. Use `update_reference_and_coaching_model.py`, which refreshes corner geometry while preserving curated names/IDs/apex sides and aborts (no changes) if any curated corner does not reproduce on the new lap. See "Pipeline B" in [`docs/HOW_TO_CREATE_A_COACHING_MODEL.md`](../../docs/HOW_TO_CREATE_A_COACHING_MODEL.md).

## Prerequisites

- A **reference lap** parquet for the target circuit must already exist under `product/data/reference-laps/`. Follow [`EXTRACT_AND_STORE_REFERENCE_LAP.md`](EXTRACT_AND_STORE_REFERENCE_LAP.md) first.

## Procedure

### 1. Run the generator

```bash
python3 dev/scripts/generate_track_coaching_model_from_reference.py \
  --reference-lap product/data/reference-laps/<track-slug>_<car-id>_time_<MM>.<SS>.<mmm>.parquet \
  --track-id <track-slug> \
  --layout-id lmu-default \
  --car-id <car-id> \
  --out product/data/track-coaching/<track-slug>_<car-id>.json \
  --diagnostics-out product/data/track-coaching/<track-slug>_<car-id>.diagnostics.txt
```

Example (Lusail):
```bash
python3 dev/scripts/generate_track_coaching_model_from_reference.py \
  --reference-lap product/data/reference-laps/lusail-international-circuit_dkr-engineering-4-elms25_time_01.52.200.parquet \
  --track-id lusail-international-circuit \
  --layout-id lmu-default \
  --car-id dkr-engineering-4-elms25 \
  --out product/data/track-coaching/lusail-international-circuit_dkr-engineering-4-elms25.json \
  --diagnostics-out product/data/track-coaching/lusail-international-circuit_dkr-engineering-4-elms25.diagnostics.txt
```

### 2. Review the diagnostics

The diagnostics file lists every detected corner in one line each:

```
t1 apex=809m start=747m end=865m min=117.4kph entry=133.0kph exit=134.5kph ...
```

Cross-check:
- Corner count matches your knowledge of the circuit.
- Apex distances are plausible (compare against a lap map or circuit guide).
- `min_speed_kph` values are realistic for each corner type.

### 3. Add real corner names (optional but recommended)

Open the generated JSON and replace the auto-generated `"name": "t1"` labels with real corner names:

```json
{ "id": "t1", "name": "Turn 1", "apex_m": 809, ... }
```

See `circuit-of-the-americas_dkr-engineering-4-elms25.json` for a fully-named example.

### 4. Commit

```
feat(coaching): generate Lusail track coaching model
```

## Detection algorithm

The generator uses `throttle_brake_v1` when throttle/brake columns are present (all LMU sessions):
- A corner event is any brake application > 15% or throttle lift < 90%.
- Adjacent events are merged if brake never fully releases to 0% between them (chicanes).
- Apex = speed minimum within the corner zone.

Falls back to `speed_local_minimum_v1` (smoothed speed local minima) for sessions without brake/throttle data.

## Known limitations

- `apex_side` (left/right) defaults to `right` and is not inferred automatically — mark it for review.
- Multi-apex complexes appear as separate corners.
- Very fast chicanes with brief throttle lifts may be merged or missed — check the diagnostics.
