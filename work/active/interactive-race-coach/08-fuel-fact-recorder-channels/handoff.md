# Handoff — Slice 08: Fuel Fact Recorder Channels

## What is on disk now

- **`product/python/lap_telemetry/recorder/connect.py`**: `Frame` dataclass extended with 5 nullable fields: `fuel_l`, `fuel_capacity_l`, `session_type`, `session_time_remaining_s`, `race_laps_total`. LMU `read_frame()` populates these from `mFuel`, `mFuelCapacity`, `mSession`, `mSessionTimeRemaining`, `mMaxLaps`. RF2 `read_frame()` sets fuel fields to `None` (not exposed in rF2 SHM).
- **`product/python/lap_telemetry/recorder/writer.py`**: Parquet schema updated with 5 new nullable columns. `SessionWriter.append()` writes the new fields.
- **`product/python/lap_telemetry/coach/frames_to_parquet.py`**: New columns included in frame-to-Parquet conversion.
- **`product/python/lap_telemetry/coach/fuel_facts.py`**: New module with:
  - `FuelFacts` dataclass
  - `compute_fuel_facts(source)` — accepts Parquet path or `list[Frame]`
  - `session_type_str(code)` — maps numeric session types to strings
  - `_classify_status(laps_remaining)` — OK/WARNING/CRITICAL/UNKNOWN
  - `_format_facts(facts)` — human-readable output
  - CLI: `python3 -m lap_telemetry.coach.fuel_facts <path> [--json]`
- **`dev/scripts/test_fuel_facts.py`** + **`.js`**: 80 assertions covering Frame fields, session mapping, status classification, compute from frames, compute from Parquet, round-trip, backward compatibility, CLI invocation.

## Feature flags

No feature flags — the new fields are always nullable, backward-compatible.

## New helpers worth knowing about

- `_optional_int(obj, attr)` in `connect.py` — reads int attribute, returns `None` if missing or ≤ 0.
- `_positive_float(obj, attr)` — reads float attribute, returns `None` if missing or ≤ 0.
- `_valid_session_type(obj, attr)` — reads int attribute, returns `None` if outside 0–10 range.
- `_read_sidecar(parquet_path)` in `fuel_facts.py` — reads JSON sidecar next to a Parquet file for track name and session metadata.

## Deferred TODOs

- Pit status fields (`mPitState`, `mInPits`, `mPitLimiter`) — deferred to a later pit-window slice.
- Per-lap fuel consumption model — current implementation uses simple average; future slices may refine.
- Track name for Parquet-based facts reads from JSON sidecar; if sidecar is missing, falls back to "unknown".

## Test command

```bash
bash scripts/test-summary.sh --feature interactive-race-coach
```