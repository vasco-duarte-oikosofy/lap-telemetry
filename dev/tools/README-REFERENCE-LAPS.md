# Export Reference Laps

This guide explains how to generate the reference lap parquet files loaded by the comparison app.

## Overview

`dev/scripts/export_fastest_reference_laps.py` scans all session parquets in `dev/sessions/` and `sessions/`, finds the fastest complete lap per track, and writes one parquet file per track to `product/data/reference-laps/`.

Each output file is named:

```
<track-slug>_<vehicle-slug>_time_<mm>.<ss>.<xxx>.parquet
```

Example:
```
circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet
```

The vehicle slug is derived from the sidecar JSON's `vehicle_name` field so users know which car produced the reference lap.

---

## Quick Start

```bash
python dev/scripts/export_fastest_reference_laps.py
```

Output goes to `product/data/reference-laps/`. The script prints which lap it selected for each track:

```
Track: circuit-de-barcelona  (14 sessions)
  Fastest: lap 3 in session_20260517T080343Z_circuit-de-barcelona_lmu.parquet (DKR Engineering #4:ELMS25) -> 96.456s
  Exported 4842 rows -> product/data/reference-laps/circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet
```

If a track already has an output file with the same name (same lap time), it is silently overwritten — the script is safe to re-run.

---

## When to Re-run

Re-run after:
- Recording a faster lap on any track
- Adding new sessions to `dev/sessions/` or `sessions/`
- Changing the vehicle (output filename will differ)

After re-running, commit the updated `product/data/reference-laps/` files. Remove any stale files for the same track with an older time.

---

## How the Script Works

### 1. Collect sessions

Scans `dev/sessions/` and `sessions/` for files matching `session_*_lmu.parquet`. Groups them by track slug extracted from the filename.

### 2. Find complete laps

For each session, a lap is considered complete if:
- `lap_number >= 1`
- `lap_time_s > 60.0`
- At least 100 data points

An additional row-count filter drops partial laps whose row count is below 95% of the per-session median — this catches sessions where the lap counter incremented mid-lap.

### 3. Pick the fastest lap

The lap with the lowest `lap_time_s` across all sessions for that track is selected.

### 4. Read vehicle name

The sidecar JSON (`session_*.json`) alongside the winning session is read for `vehicle_name`, which is slugified for the output filename.

### 5. Write output

The selected lap's rows are written as a new parquet file. Column schema is identical to the source session — the app loads it using the same hyparquet reader.

---

## Loading a Reference Lap in the App

In `product/dist/compare.html`, use the file picker to load any file from `product/data/reference-laps/` as either the session lap or the reference lap. The vehicle name in the filename tells you what car produced it.

---

## See Also

- `dev/scripts/export_fastest_reference_laps.py` — the automated export script
- `dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md` — manual procedure for a single circuit
- `product/data/reference-laps/` — output directory
- `dev/tools/README-GENERATE-OUTLINE.md` — analogous guide for track outlines
