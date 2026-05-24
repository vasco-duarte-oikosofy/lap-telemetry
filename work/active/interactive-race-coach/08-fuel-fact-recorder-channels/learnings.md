# Learnings — Slice 08: Fuel Fact Recorder Channels

## L1: Track name is NOT in the Parquet schema

The `SessionWriter` stores `track_name`, `vehicle_name`, and `sim` in the JSON sidecar, not in the Parquet columns. This means `compute_fuel_facts()` for Parquet sources must try to read the `.json` sidecar file next to the `.parquet` file. Falls back to `"unknown"` if sidecar is missing.

## L2: Nullability is the key to backward compatibility

All 5 new `Frame` fields default to `None`. The new Parquet columns are nullable. Old Parquet files without these columns load fine — PyArrow fills missing columns with null. This pattern should be followed for future extensions.

## L3: NumPy/pandas import warnings are noisy but harmless

The test runner emits NumPy 1.x/2.x compatibility warnings when `pyarrow` triggers `pandas` import. These are non-fatal. The `frames_to_parquet` function uses `pa.table()` which can trigger this path. Tests still pass.

## L4: `_optional_int` vs `_valid_session_type`

We introduced `_optional_int` (returns `None` for ≤ 0 values) for `mMaxLaps`, and `_valid_session_type` (returns `None` for values outside 0–10) for `mSession`. These are subtly different — `mMaxLaps` of 0 means "no race lap limit" (should be None), but `mSession` of 0 means "practice" (valid). Next agent: be aware of this distinction.

## L5: Fuel-per-lap uses simple average

Fuel per lap = (fuel_at_start − fuel_at_end) / laps_completed. This includes in-lap/out-lap variation. A future slice may want per-lap fuel deltas for more precision.

## L6: `_classify_status` threshold boundary

2.0 laps remaining → WARNING (not CRITICAL). 5.0 laps remaining → WARNING (not OK). These boundary conditions are important to get right.