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

### 1. Survey laps across all sessions for the circuit

Run `explore_and_export_laps.py` on **every** session file for the target circuit. The fastest lap must come from the fastest lap across **all** sessions, not just one — a suboptimal session will produce a suboptimal reference.

```bash
python3 dev/scripts/explore_and_export_laps.py \
    dev/sessions/<session-file>.parquet
```

This prints a table of every lap with its lap number, time, point count, distance, and completeness status. The script also identifies the fastest complete lap automatically.

Compare the fastest-lap times from each session and pick the overall fastest lap number and its source session file.

### 2. Extract the lap

```bash
python3 dev/scripts/extract_reference_lap.py \
    dev/sessions/<session-file>.parquet \
    --lap <lap-number> \
    --out /tmp/ref_lap_extract.parquet
```

Use the `--lap` flag with the lap number from step 1. If the same lap number appears in multiple stints, the script automatically picks the segment with the shortest lap time.

### 3. Verify the extracted lap time

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

### 4. Replace the old reference-lap file

```bash
rm product/data/reference-laps/<track-slug>_time_<old-time>.parquet
cp /tmp/ref_lap_extract.parquet \
   product/data/reference-laps/<track-slug>_time_<new-time>.parquet
```

### 5. Clean up

```bash
rm /tmp/ref_lap_extract.parquet
```

### 6. Commit

Commit the deletion of the old file and addition of the new one. The commit message should include the track, old time, and new time:

```
ref: update circuit-de-barcelona reference lap 01.36.810 → 01.36.456
```