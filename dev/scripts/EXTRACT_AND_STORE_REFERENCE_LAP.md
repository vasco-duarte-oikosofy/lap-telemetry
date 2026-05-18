# Extracting and Storing a Reference Lap

A **reference lap** is the fastest known clean lap for a given circuit, stored as a single-lap Parquet file under `product/data/reference-laps/`. It is used by the compare view and delta-time analysis as the benchmark lap.

## Naming convention

```
product/data/reference-laps/<track-slug>_time_<MM>.<SS>.<mmm>.parquet
```

- `<track-slug>`: circuit name as it appears in session filenames (e.g. `circuit-de-barcelona`).
- `<MM>.<SS>.<mmm>`: fastest lap time formatted as `minutes.seconds.milliseconds`.

When a new fastest time is found, **replace the old file** (delete it) and create a new one with the updated time in the filename. There should be at most one reference-lap file per track.

## Procedure

### 1. Survey laps in the session

```bash
python3 dev/scripts/extract_reference_lap.py \
    dev/sessions/<session-file>.parquet --segment 1
```

This prints every segment with its lap number, row count, and duration. Scan the output and identify the fastest complete lap (lowest duration, typically ≥60 s with ≥4 800 rows).

### 2. Find the segment number for that lap

Segments are 1-indexed in the order they appear in the file. Note the segment number of the fastest lap from the output above.

### 3. Extract the lap

```bash
python3 dev/scripts/extract_reference_lap.py \
    dev/sessions/<session-file>.parquet \
    --segment <N> \
    --out /tmp/ref_lap_extract.parquet
```

### 4. Verify the extracted lap time

```bash
python3 -c "
import pyarrow.parquet as pq
t = pq.read_table('/tmp/ref_lap_extract.parquet')
duration = max(t.column('lap_time_s').to_pylist())
m, s = divmod(duration, 60)
print(f'{int(m)}:{s:06.3f}')
"
```

Confirm the time matches your expectation.

### 5. Replace the old reference-lap file

```bash
rm product/data/reference-laps/<track-slug>_time_<old-time>.parquet
cp /tmp/ref_lap_extract.parquet \
   product/data/reference-laps/<track-slug>_time_<new-time>.parquet
```

### 6. Clean up

```bash
rm /tmp/ref_lap_extract.parquet
```

### 7. Commit

Commit the deletion of the old file and addition of the new one. The commit message should include the track, old time, and new time:

```
ref: update circuit-de-barcelona reference lap 01.36.810 → 01.36.456
```