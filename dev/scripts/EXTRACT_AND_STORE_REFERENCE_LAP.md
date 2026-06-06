# Extracting and Storing a Reference Lap

A **reference lap** is the fastest known clean lap for a given circuit and car, stored as a single-lap Parquet file under `product/data/reference-laps/`. It is used by the compare view and delta-time analysis as the benchmark lap.

## ⚠️ Cardinal rule: one reference lap per export run

**We NEVER export all reference laps at the same time.** Every export run targets exactly one (track, vehicle) combo and may change at most one reference file. Bulk re-export silently corrupted the entire curated set once (bug 22: restarted-session stints merged into single files, curated refs overwritten, wrong-car laps exported) — the export script now refuses multi-combo targets and runs a **mandatory post-export audit** that fails the run if more than one reference changed on disk. If the audit ever fails, recover `product/data/reference-laps/` via git before committing anything.

## Naming convention

```
product/data/reference-laps/<track-slug>_<vehicle-slug>_time_<MM>.<SS>.<mmm>.parquet
```

- `<track-slug>`: circuit name as it appears in session filenames (e.g. `circuit-de-barcelona`).
- `<vehicle-slug>`: slugified `vehicle_name` from the session's JSON sidecar (e.g. `dkr-engineering-4-elms25`).
- `<MM>.<SS>.<mmm>`: fastest lap time formatted as `minutes.seconds.milliseconds`.

When a new fastest time is found, **replace the old file** (delete it) and create a new one with the updated time in the filename. There should be at most one reference-lap file per (track, vehicle).

## Procedure (preferred): `export_fastest_reference_laps.py`

One command per circuit — pass the session file(s) to consider, all from the same track and car:

```powershell
python dev/scripts/export_fastest_reference_laps.py `
    sessions/session_20260606T064918Z_autdromo-jos-carlos-pace_lmu_practice.parquet
```

The script:

1. **Refuses to run** if the targets span more than one (track, vehicle) combo, or if no targets are given (`--help` shows usage).
2. Finds complete laps **per contiguous segment** (never by grouping `lap_number` — see Pitfalls), validates each candidate's wall-clock span against its claimed time, and picks the fastest.
3. Keeps the existing reference unless the new lap is faster by more than 1 ms; when replacing, it deletes the superseded file.
4. **Audits the output directory** before/after and hard-fails if anything other than that single reference changed:

```
AUDIT: 1 reference lap changed (added: [...], superseded: [...]). OK.
```

A run is only valid if it ends with an `AUDIT:` line reporting 0 or 1 changed laps. Then validate the whole folder and commit:

```powershell
python dev/scripts/validate_reference_laps.py
```

This checks every reference lap for internal consistency (single contiguous lap, duration matches filename) and provenance (a source session exists on the same track, in the same car, with a matching lap time).

## Pitfalls

### Multi-shard sessions

Long or interrupted recording sessions produce many `.part0.parquet`, `.part1.parquet`, … shard files instead of a single `.parquet`. The extraction scripts require a single merged file. Merge first:

```python
import pyarrow.parquet as pq, pyarrow as pa, glob, os

slug = "lusail-international-circuit"  # or any session slug
parts = sorted(glob.glob(f"sessions/session_*{slug}*.part*.parquet"))
merged = pa.concat_tables([pq.read_table(p) for p in parts])
os.makedirs("dev/sessions", exist_ok=True)
pq.write_table(merged, f"dev/sessions/{slug}_merged.parquet")
```

Then use `dev/sessions/{slug}_merged.parquet` as the input to the steps below. Delete the temp file when done.

### Multi-stint sessions

Many sessions contain two or more stints (pit stops rejoining the track). When this happens, the same `lap_number` value appears in multiple segments — e.g. lap 3 in stint 1 might be 1:36.456 while lap 3 in stint 2 is 1:37.435. If you group by `lap_number` and take `max(lap_time_s)`, you get the **slower** stint, hiding the actually fastest segment.

**Always use segment-based analysis** (`extract_reference_lap.py --segment` listing) or the `--lap` flag (which picks the shortest-time segment for a given lap number). Never rely on groupby-lap-number aggregation.

### Truncated sessions

Some sessions end mid-lap when the driver exits. The resulting "lap" can have a full `lap_distance_m` (the car crossed the start/finish line) but an impossibly short `lap_time_s` — e.g. a 64-second "lap" at Imola where 1:40 is realistic. These are flagged ✅ Complete by `explore_and_export_laps.py` (time > 60s) but are not real laps.

**Validate the fastest lap** by cross-checking:
- Does its time make sense for the circuit? (e.g. sub-1:20 at Barcelona is impossible in GT3)
- Is the row count consistent with other complete laps in the same session?
- Is the `lap_distance_m` in the right range?

## Procedure (manual fallback, single circuit)

### 1. Survey laps across all sessions for the circuit

Run `extract_reference_lap.py` with `--valid-only` on **every** session file for the target circuit. Pass any `--segment` value just to trigger the listing; the segment listing prints regardless.

```powershell
python dev/scripts/extract_reference_lap.py `
    sessions/<session-file>.parquet --segment 1 --valid-only
```

Each segment is tagged `[valid]` or `[INVALID]`. A segment is valid only when **every row** in it has `lap_valid=True` — a single track-limit violation marks the whole segment `[INVALID]`. Compare the fastest `[valid]` segment across all sessions and pick that lap.

⚠️ **Multi-stint sessions** (see Pitfalls above): the same `lap_number` can appear in multiple segments. `extract_reference_lap.py` lists them as separate segments so you can compare them individually — always use `--segment N` rather than `--lap N` when a lap number repeats.

### 2. Extract the lap

```powershell
python dev/scripts/extract_reference_lap.py `
    sessions/<session-file>.parquet `
    --segment <N> --valid-only `
    --out sessions/tmp_ref_lap.parquet
```

Use `--segment N` with the segment number from step 1. Add `--valid-only` so the script refuses to extract if the segment contains any invalid rows — a safeguard against accidentally storing a lap with track-limit violations. If the lap number is unique in the session, `--lap <lap-number> --valid-only` works equally well.

### 3. Verify the extracted lap time

The script prints a `Lap time:` line at the end, e.g.:

```
Lap time: 1:36.456
```

Confirm this matches your expectation and is realistic for the circuit. If you want to double-check independently:

```bash
python3 -c "
import pyarrow.parquet as pq
t = pq.read_table('/tmp/ref_lap_extract.parquet')
duration = max(t.column('lap_time_s').to_pylist())
m, s = divmod(duration, 60)
print(f'{int(m)}:{s:06.3f}')
"
```

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

## Updating several circuits

There is **no bulk procedure** — see the cardinal rule at the top. To update more than one circuit, run the preferred procedure once per circuit, in separate runs, and give each circuit its own commit. Never script a loop that rewrites the whole `product/data/reference-laps/` folder in one pass (that is exactly what caused bug 22).