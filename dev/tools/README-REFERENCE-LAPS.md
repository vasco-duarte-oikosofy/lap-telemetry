# Export Reference Laps

This guide explains how to generate the reference lap parquet files loaded by the comparison app.

## ⚠️ Cardinal rule: one reference lap per export run

**We NEVER export all reference laps at the same time.** A single run targets exactly one (track, vehicle) combo and may change at most one reference file. A bulk re-export once corrupted the entire curated set (bug 22: multi-stint laps merged into single files, curated refs silently overwritten, wrong-car laps exported). The script enforces this:

- It **refuses to run** if the given sessions span more than one (track, vehicle) combo.
- After exporting, a **mandatory audit** compares `product/data/reference-laps/` before/after and hard-fails (non-zero exit) if anything other than that single reference changed.

A run is only valid if it ends with:

```
AUDIT: 1 reference lap changed (added: [...], superseded: [...]). OK.
```

(or `AUDIT: 0 reference laps changed.` when the existing reference was already faster).

## Overview

`dev/scripts/export_fastest_reference_laps.py` takes the session parquet(s) you point it at — all from the same track and car — finds the fastest complete lap, and writes one parquet file to `product/data/reference-laps/`.

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
# the normal case: export from the session you just recorded
python dev/scripts/export_fastest_reference_laps.py \
    sessions/session_20260606T064918Z_autdromo-jos-carlos-pace_lmu_practice.parquet
```

Several sessions of the **same** track + car can be passed together (files and/or directories); the fastest lap across all of them wins:

```bash
python dev/scripts/export_fastest_reference_laps.py \
    sessions/session_*_fuji-speedway_lmu*.parquet
```

Running with no arguments prints usage and exits — there is intentionally no "export everything" mode.

Example output:

```
Track: autdromo-jos-carlos-pace  Vehicle: dkr-engineering-4-elms25  (1 sessions)
  Fastest: lap 16 in session_20260606T064918Z_autdromo-jos-carlos-pace_lmu_practice.parquet -> 92.367s
  Exported 4596 rows -> product/data/reference-laps/autdromo-jos-carlos-pace_dkr-engineering-4-elms25_time_01.32.367.parquet

AUDIT: 1 reference lap changed (added: [...], superseded: []). OK.
```

After exporting, validate the whole folder before committing:

```bash
python dev/scripts/validate_reference_laps.py
```

This checks every reference lap for internal consistency (single contiguous lap, duration matches the filename) and provenance (a source session exists for the same track, in the same car, with a matching lap time).

---

## When to run

Run after recording a session in which you may have beaten the current reference for that track + car. The script keeps the existing reference unless your new lap is faster by more than 1 ms, so it is safe to run speculatively — for **one** combo at a time.

To update several circuits, run once per circuit and give each its own commit. Never script a loop that rewrites the whole `product/data/reference-laps/` folder in one pass.

---

## How the Script Works

### 1. Scope guard

Targets are grouped by (track slug from the filename, vehicle slug from the sidecar JSON). More than one group → abort before anything is written.

### 2. Find complete laps

Laps are detected per **contiguous segment** of `lap_number` — never by grouping on lap number, because sessions recorded across sim restarts repeat lap numbers and grouping merges two different laps into one (the bug 19/22 corruption). A candidate segment must have:

- `lap_number >= 1`
- authoritative lap time > 60.0 s (`scoring_last_lap_time_s` preferred over `max(lap_time_s)`)
- at least 100 data points
- a wall-clock span (`session_time_s`) that agrees with the claimed lap time (rejects restart-truncated segments with bogus times)

An additional row-count filter drops partial laps below 95 % of the per-session median.

### 3. Pick the fastest lap

The fastest valid segment across all given sessions wins. If the existing reference for this (track, vehicle) is not beaten by more than 1 ms, nothing is written.

### 4. Write output and supersede

The winning segment's rows are **sliced** out and written as a new parquet file (column schema identical to the source session — the app loads it with the same hyparquet reader). Older reference files for the same (track, vehicle) are deleted so at most one exists.

### 5. Mandatory audit

The output directory snapshot from before the run is compared with the after state. Any added/removed/modified file outside the target (track, vehicle), more than one added file, or any in-place overwrite fails the run with `AUDIT FAILED`. If that ever happens, recover `product/data/reference-laps/` via git before committing.

---

## Loading a Reference Lap in the App

In `product/dist/compare.html`, use the file picker to load any file from `product/data/reference-laps/` as either the session lap or the reference lap. The vehicle name in the filename tells you what car produced it.

---

## See Also

- `dev/scripts/export_fastest_reference_laps.py` — the automated export script
- `dev/scripts/validate_reference_laps.py` — post-export folder validation
- `dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md` — workflow doc + manual fallback procedure
- `product/data/reference-laps/` — output directory
- `work/completed/bugs/22-export-overwrites-all-reference-laps/bug.md` — why these guards exist
- `dev/tools/README-GENERATE-OUTLINE.md` — analogous guide for track outlines
