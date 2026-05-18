# Extracting and Storing a Reference Lap

A **reference lap** is the fastest known clean lap for a given circuit, stored as a single-lap Parquet file under `product/data/reference-laps/`. It is used by the compare view and delta-time analysis as the benchmark lap.

## Naming convention

```
product/data/reference-laps/<track-slug>_time_<MM>.<SS>.<mmm>.parquet
```

- `<track-slug>`: circuit name as it appears in session filenames (e.g. `circuit-de-barcelona`).
- `<MM>.<SS>.<mmm>`: fastest lap time formatted as `minutes.seconds.milliseconds`.

When a new fastest time is found, **replace the old file** (delete it) and create a new one with the updated time in the filename. There should be at most one reference-lap file per track.

## Pitfalls

### Multi-stint sessions

Many sessions contain two or more stints (pit stops rejoining the track). When this happens, the same `lap_number` value appears in multiple segments — e.g. lap 3 in stint 1 might be 1:36.456 while lap 3 in stint 2 is 1:37.435. If you group by `lap_number` and take `max(lap_time_s)`, you get the **slower** stint, hiding the actually fastest segment.

**Always use segment-based analysis** (`extract_reference_lap.py --segment` listing) or the `--lap` flag (which picks the shortest-time segment for a given lap number). Never rely on groupby-lap-number aggregation.

### Truncated sessions

Some sessions end mid-lap when the driver exits. The resulting "lap" can have a full `lap_distance_m` (the car crossed the start/finish line) but an impossibly short `lap_time_s` — e.g. a 64-second "lap" at Imola where 1:40 is realistic. These are flagged ✅ Complete by `explore_and_export_laps.py` (time > 60s) but are not real laps.

**Validate the fastest lap** by cross-checking:
- Does its time make sense for the circuit? (e.g. sub-1:20 at Barcelona is impossible in GT3)
- Is the row count consistent with other complete laps in the same session?
- Is the `lap_distance_m` in the right range?

## Procedure (single circuit)

### 1. Survey laps across all sessions for the circuit

Run `explore_and_export_laps.py` on **every** session file for the target circuit. The fastest lap must come from the fastest lap across **all** sessions, not just one — a suboptimal session will produce a suboptimal reference.

```bash
python3 dev/scripts/explore_and_export_laps.py \
    dev/sessions/<session-file>.parquet
```

This prints a table of every lap with its lap number, time, point count, distance, and completeness status. The script also identifies the fastest complete lap automatically.

⚠️ **The "Fastest" line can be wrong in multi-stint sessions** (see Pitfalls above). If two sessions report the same lap number with different times, use `extract_reference_lap.py` to inspect the segment-level detail:

```bash
python3 dev/scripts/extract_reference_lap.py \
    dev/sessions/<session-file>.parquet --segment 1
```

This lists every segment, which lets you spot the fastest individual segment even when lap numbers repeat across stints.

Compare across all sessions and pick the overall fastest lap number and its source session file.

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

Confirm the time matches your expectation and is realistic for the circuit.

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

## Procedure (all circuits)

To update reference laps for every circuit at once:

### 1. List current reference laps

```bash
ls product/data/reference-laps/
```

Note each circuit's current time.

### 2. Survey all sessions by circuit

For each circuit slug in `dev/sessions/`, run `explore_and_export_laps.py` on every session and collect the fastest-lap time. Cross-reference with `extract_reference_lap.py --segment 1` for sessions where the "Fastest" line looks suspiciously fast or comes from a multi-stint session.

### 3. Compare and decide

For each circuit, compare the fastest available lap time against the current reference. Only update if the new time is **strictly faster** (lower). If no session beats the current reference, leave it unchanged.

### 4. Extract, verify, replace, commit

For each circuit that needs updating, follow steps 2–6 of the single-circuit procedure above. Each circuit gets its own commit.