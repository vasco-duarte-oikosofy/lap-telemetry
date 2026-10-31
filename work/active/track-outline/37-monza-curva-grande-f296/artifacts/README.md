# Slice 37 artifacts

- `seed_model_from_curated.py` — writes the F296 coaching model from the curated
  Ginetta one (copies names, IDs, apex sides and the two `target_throttle_pct: 100`
  flat markers, and points it at the new reference). Run once; the geometry is
  then refreshed by `dev/scripts/update_reference_and_coaching_model.py --ref …`.

There are no images: this slice changes reference/coaching data only, not the
outline geometry that the map draws.
