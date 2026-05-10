# M2 — Write Loop

**Goal:** `lap-telemetry record` writes a Parquet file + JSON sidecar per stint,
crash-safe via periodic shard flushing. M1 printed frames; M2 persists them.

---

## Read before starting

Read these files in full before touching any code:

| File | Why |
|---|---|
| `DESIGN.md` §4.1, §5.1, §5.2, §6 | Column schema, sidecar format, CLI surface, shard/session lifecycle |
| `lap_telemetry/recorder/connect.py` | `Frame` dataclass fields, `LMUConnection.start()` / `RF2Connection.start()` — see `create(1)` calls to change |
| `lap_telemetry/recorder/record.py` | The poll loop to extend — buffer replaces `print()` |
| `lap_telemetry/cli.py` | Where to add `--out-dir` |
| `pyproject.toml` | Where to add `pyarrow` dependency |
| `pyLMUSharedMemory/lmu_mmap.py` | `MMapControl.create()` signature: `0` = copy access (safe), `1` = direct access (can tear). Copy mode copies buffer only when sim update events fire and vehicle counts agree. |

---

## Steps

### 1. Add pyarrow dependency

In `pyproject.toml`, add to `dependencies`:

```toml
dependencies = ["pyarrow>=14"]
```

Then reinstall: `pip install -e .`

---

### 2. Switch to copy-mode mmap in `connect.py`

In `LMUConnection.start()`, change `create(1)` → `create(0)`.

In `RF2Connection.start()`, change `create(1)` → `create(0)` for all three mmaps
(`self._scor`, `self._tele`, `self._ext`).

`create(0)` keeps a copied buffer and only refreshes it when the sim's update
event flags are set and vehicle counts agree — no torn rows.

---

### 3. Create `lap_telemetry/recorder/writer.py`

New module responsible for buffering, shard flushing, and session finalisation.

**Public API the record loop needs:**

```python
class SessionWriter:
    def __init__(self, out_dir: Path, sim: str, track: str, rate_hz: float): ...
    def append(self, frame: Frame) -> None: ...
    def flush_shard(self) -> None:           # called every 30 s
    def close(self) -> tuple[Path, Path]:    # returns (parquet_path, json_path)
```

**Parquet schema** — columns from `Frame` that map to DESIGN.md §5.1 names.
Use `pyarrow` schema defined once as a module-level constant:

| Parquet column | Frame field | Arrow type |
|---|---|---|
| `session_time_s` | `session_time_s` | `float64` |
| `lap_number` | `lap_number` | `int32` |
| `lap_distance_m` | `lap_distance_m` | `float32` |
| `lap_time_s` | `lap_time_s` | `float32` |
| `speed_kph` | `speed_kph` | `float32` |
| `throttle_norm` | `throttle_norm` | `float32` |
| `brake_norm` | `brake_norm` | `float32` |
| `steering_norm` | `steering_norm` | `float32` |
| `gear` | `gear` | `int8` |
| `engine_rpm` | `engine_rpm` | `float32` |

`clutch_norm` is in the final schema (DESIGN.md) but not in `Frame` yet — skip it
for M2. Do not add a null column; expand `Frame` in a later milestone when the
SHM field is wired up.

**Shard files:** `<out_dir>/<session_stem>.part<N>.parquet`
Write with `pyarrow.parquet.write_table(..., compression="snappy")`.

**Session finalisation (`close`):**
1. Flush any remaining buffer rows as the last shard.
2. Read all shards with `pyarrow.parquet.read_table`.
3. Concatenate with `pyarrow.concat_tables`.
4. Write final `<session_stem>.parquet` (Snappy).
5. Delete the `.part*.parquet` shard files.
6. Write `<session_stem>.json` sidecar (see §5.2 below).
7. Return both paths.

**Session stem naming:** `session_<UTC-iso-compact>_<track-slug>_<sim>`
e.g. `session_20260509T175511Z_bahrain-international-circuit_lmu`

Track slug: lowercase, spaces → hyphens, strip non-alphanumeric except hyphens.

**JSON sidecar** (DESIGN.md §5.2 subset for M2 — omit fields not yet available):

```json
{
  "schema_version": "1",
  "recorder_version": "<from lap_telemetry.__version__>",
  "started_utc": "<ISO 8601>",
  "ended_utc": "<ISO 8601>",
  "sim": "lmu",
  "track": "<track_name from Frame>",
  "vehicle_name": "<vehicle_name from Frame>",
  "sample_rate_hz": 50,
  "row_count": 12345,
  "lap_count": 3
}
```

`track_length_m` and `vehicle_class` are not in `Frame` yet — omit them for M2.

---

### 4. Update `record.py`

Accept `out_dir: Path` parameter in `run()`.

Replace `print(_format_frame(frame))` with:
```python
writer.append(frame)
```

Keep the lap-boundary and track/vehicle-change `print()` lines — they are useful
live feedback and cost nothing.

Add periodic flush: track `last_flush_time`; when `time.monotonic() - last_flush_time >= 30`,
call `writer.flush_shard()` and reset the timer.

On session change (track or vehicle differs from last seen values), call
`writer.close()`, print the output paths, open a new `SessionWriter`, reset
lap/track/vehicle tracking state.

On shutdown (the `finally` block), call `writer.close()` and print the paths.

Drop frames where `frame.in_realtime` is `False` or `frame.paused` is `True` —
do not append them to the writer. (M1 already skips `None` frames; add this
guard before `writer.append`.)

---

### 5. Update `cli.py`

Add `--out-dir` to the `record` subparser:

```python
rec.add_argument(
    "--out-dir",
    type=Path,
    default=Path("sessions"),
    help="Directory to write session files (default: ./sessions).",
)
```

Pass `args.out_dir` through to `run()`.

`run()` should `mkdir(parents=True, exist_ok=True)` the directory on startup.

---

## Drop conditions (do not write these frames)

| Condition | Source field | Action |
|---|---|---|
| Not in realtime | `frame.in_realtime == False` | skip |
| Paused | `frame.paused == True` | skip |
| No player found | `read_frame()` returns `None` | skip (already handled) |

Do not write a dedup / `mDeltaTime == 0` guard for M2 — that field isn't in
`Frame` yet. Duplicate frames at 50 Hz are harmless in Parquet; filter at query
time if needed.

---

## Verification

After implementing, with the sim running:

```powershell
lap-telemetry record --out-dir ./sessions
# drive a lap or two, Ctrl+C
```

Expected:
- `sessions/session_<...>.parquet` exists, is readable
- `sessions/session_<...>.json` exists, contains correct metadata

Quick read-back check (no analyzer yet):

```python
import pyarrow.parquet as pq
t = pq.read_table("sessions/<file>.parquet")
print(t.schema)
print(t.num_rows)
print(t.column("lap_number").to_pylist()[-5:])
```

M2 is done when the Parquet file loads, has the right schema, and `lap_number`
increments correctly across boundaries.

---

## M2 additions (post-recording gaps found in first live test)

### A. Lap validity flag

Add `lap_valid: bool` to `Frame` from `scor_v.mCountLapFlag` (0 = invalid, >0 = valid/penalised).
Add `lap_valid` column (`bool`) to the Parquet schema and `SessionWriter.append()`.

Source fields:
- LMU: `scor.vehScoringInfo[idx].mCountLapFlag`
- rF2: `self._scor.data.mVehicles[idx].mCountLapFlag`

### B. World position (trajectory visualisation)

Add `pos_x_m`, `pos_y_m`, `pos_z_m` (`float32` each) to `Frame` from `tele_v.mPos`.
Add matching columns to the Parquet schema.

Source fields:
- LMU: `tele_v.mPos.x / .y / .z`
- rF2: `tele_v.mPos.x / .y / .z`

### C. `lap-telemetry summary` subcommand

New subcommand: `lap-telemetry summary <parquet-file>`

Reads the Parquet file (and JSON sidecar if present) and prints:

```
track  : Circuit de Barcelona
vehicle: DKR Engineering #4:ELMS25
sim    : lmu
period : 2026-05-10T06:32:43Z → 2026-05-10T06:36:43Z
rows   : 12000  (240.0 s at 50.0 Hz)

 lap   frames   duration    valid
   0       32   0:00.640    —
   1     5467   1:49.346    no
   2     5116   1:42.369    yes
   3     1385   0:27.599    —
```

Lap 0 and the last lap are marked `—` (incomplete: no prior/subsequent lap boundary in the file).
`valid` column shows `—` when the `lap_valid` column is absent (files recorded before this addition).

Implementation:
- `lap_telemetry/summary.py` — `run(path: Path) -> int`
- `cli.py` — add `summary` subparser with a `file` positional argument, dispatch to `summary.run()`

---

## M2 acceptance test (run this before closing M2)

Prerequisites: LMU running, car on track, at least 2 complete laps available.

```powershell
lap-telemetry record --out-dir ./sessions
# drive 2+ laps, then Ctrl+C cleanly from this terminal
```

Then:

```powershell
lap-telemetry summary sessions/<latest>.parquet
```

Pass criteria:
- `rows` count is consistent with lap count × ~50 Hz × lap duration
- `lap_number` column shows at least 3 entries (out-lap, lap 1, lap 2+)
- first and last laps show `-` (incomplete), middle laps show `yes` or `no`
- at least one lap shows `yes` (sim confirmed it as valid)
- no orphaned `.partN.parquet` files remain in `./sessions` after clean Ctrl+C

Orphan-recovery test (optional):
```powershell
# start recording, kill the terminal window (hard kill)
# then re-run record — it should print "recovering N orphaned shards" on startup
lap-telemetry record --out-dir ./sessions
# Ctrl+C immediately; check that the recovered file appears
lap-telemetry summary sessions/<recovered>.parquet
```
