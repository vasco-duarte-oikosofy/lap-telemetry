# M3 — Read path: sectors + recoverable metadata + patient multi-session recorder

**Goal:** make `lap-telemetry summary` show sector splits, make session
metadata (`track`, `vehicle_name`, `sim`, `started_utc`) survive a hard kill,
and turn the recorder into a long-running daemon that can be started before
the sim launches and produces one session file per car/track combo across an
entire driving evening.

This is the first milestone where the read path matters in earnest. M2's
acceptance test left a recovered session with `vehicle: unknown` and no
`ended_utc` — that hole closes here. M3's first live test exposed a second
hole: the recorder gated frames on `mInRealtime`, which is False in the pit
garage and the in-game menus, so a 2-lap drive produced zero output. Piece D
fixes that and turns the recorder into something you can leave running.

---

## Read before starting

Read these files in full before touching any code:

| File | Why |
|---|---|
| `DESIGN.md` §4.1, §4.2, §5.2 | Recorder behaviour, summary surface, sidecar shape |
| `m2-plan.md` Result block | What was tested, what came up short — informs M3 scope |
| `lap_telemetry/recorder/writer.py` | `SessionWriter` lifecycle and `recover_orphaned_shards`; sidecar is currently written *only* in `close()` |
| `lap_telemetry/recorder/connect.py` | Where `Frame` is built; `mLastSector1` / `mLastSector2` live on `vehScoringInfo` for both sims |
| `lap_telemetry/recorder/record.py` | When `SessionWriter` is constructed (after first frame, so `track_name` is already populated) |
| `lap_telemetry/summary.py` | Sidecar read path; the table loop where sectors will be added |

---

## Scope

Four independent pieces. (A) is required and lands first. (B) is the
sectors feature. (C) is small. (D) was added after the first live test
revealed the recorder gate was wrong; it's the work that makes the milestone
actually usable.

### A. Recoverable metadata (REQUIRED)

**Problem.** `recover_orphaned_shards` reconstructs a sidecar from the filename
stem alone, so `vehicle_name` is always `"unknown"` and `track` is the slug, not
the original string. After a hard kill the user loses the very fields they need
to identify a session.

**Approach.** Persist the sidecar throughout the session, not just at `close()`.

1. `SessionWriter.__init__` writes `<stem>.json` immediately with every field
   it knows: `schema_version`, `recorder_version`, `started_utc`, `sim`,
   `track`, `sample_rate_hz`. `vehicle_name` starts as `""` (filled in after
   the first `append`). `ended_utc` is `null`. `row_count` / `lap_count` are
   `0`. Add a top-level `"in_progress": true` flag.
2. `SessionWriter.flush_shard` updates the sidecar in place: refreshes
   `vehicle_name`, `row_count` (cumulative across shards), `lap_count`. Cost
   is one tiny JSON write per 30 s — negligible.
3. `SessionWriter.close` flips `in_progress` to `false`, sets `ended_utc`,
   recomputes `row_count` / `lap_count` from the merged final table, writes.
4. `recover_orphaned_shards` reads the existing sidecar if present; fills in
   `row_count`, `lap_count`, sets `recovered: true`, sets `ended_utc` to
   `"unknown"` (we genuinely don't know when the kill happened — better than
   inventing a value), keeps every other field. Falls back to today's
   stem-derived best effort only when no sidecar file exists.
5. `summary.py` already reads `track` and `vehicle_name` from the sidecar — no
   change needed there. It will simply get real values now.

**Why a single sidecar file (rather than a `.start.json` plus a `.json`):** one
file is simpler, atomic-write-safe, and the current `summary` and recovery
paths both already key off `<stem>.json`. The trade-off is that we rewrite the
sidecar ~once per shard flush — at ~3 KB it's free.

**Atomic write.** Use a `<stem>.json.tmp` → `os.replace(...)` swap so a crash
mid-write can never leave a half-written sidecar. (`os.replace` is atomic on
Windows since Python 3.3.)

### B. Sector splits in `summary`

**Capture.** Add `last_sector_1_s` and `last_sector_2_s` to `Frame` and the
Parquet schema. Source on both sims:
- LMU: `scor_v.mLastSector1`, `scor_v.mLastSector2`
- rF2: `scor_v.mLastSector1`, `scor_v.mLastSector2`

These hold the *previous completed lap's* sector times. So for a lap N, the
splits are read from any frame on lap N+1. Convert -1.0 (sim's "not set"
sentinel) to `NaN` at the recorder boundary.

**Schema additions:**

| Parquet column | Frame field | Arrow type |
|---|---|---|
| `last_sector_1_s` | `last_sector_1_s` | `float32` |
| `last_sector_2_s` | `last_sector_2_s` | `float32` |

(`last_sector_3_s` is not stored — it's `lap_time - s1 - s2`, computed in
summary.)

**Display.** Extend `summary.py`:

```
 lap   frames   duration       s1       s2       s3   valid
   0     8647   1:47.287        -        -        -       -
   1     5554   1:51.077   34.521   38.910   37.646     yes
   2     5144   1:42.753   31.402   34.871   36.480     yes
   3     5023   1:40.440   30.891   34.220   35.329     yes
   4     2525   0:02.166        -        -        -       -
```

For each lap N: find the *first* frame whose `lap_number == N+1`. Its
`last_sector_1_s` / `last_sector_2_s` are lap N's S1/S2. Compute S3 from the
lap's duration. First and last laps in the file show `-` (no successor frame
or no boundary, matching the existing valid-column convention).

If `last_sector_1_s` is absent from the schema (older recordings), show `-`
for all sector columns — same backward-compat pattern `summary` uses for
`lap_valid`.

### C. Doc tidy

`CLAUDE.md` reference list should add `m3-plan.md`. (DESIGN.md was tidied as
part of M3 prep — no further changes required there.)

### D. Patient recorder + multi-session per run

**Problem.** Two interlocking issues found in the M3 live test:

1. The probe gives up after 3 s, so the recorder can only be started while
   the sim is already running. The user wants to start the recorder first,
   then launch the sim and drive whenever they're ready.
2. The frame loop drops everything where `mInRealtime` is False. In LMU,
   `mInRealtime` is False during the pit-garage UI, menu screens, and
   inter-session transitions — i.e., a meaningful fraction of any normal
   driving evening. The user's first 2-lap test produced zero output because
   of this.

The use case: start the recorder once, leave it running, drive multiple
sessions (different cars, different tracks) during the evening, come back to
a directory with one self-contained `.parquet` + `.json` per car/track
combo. Each file's sidecar already carries `track` + `vehicle_name`, so a
later UI can filter on (car, track) without parsing the recorder run state.

**Approach.**

1. **Patient probe.** `--probe-timeout` defaults to `0` ("wait forever, Ctrl+C
   to abort"). Internally this is a retry loop around the existing 3 s
   `probe_and_connect` call. SIGINT during the wait exits cleanly with
   status 0. The smoke-test path keeps a finite default: `--once` implies
   `--probe-timeout 3` unless the user overrides explicitly, so
   `lap-telemetry record --once` still fails fast when the sim isn't up.

2. **New frame gate.** Drop `mInRealtime` entirely. Keep skipping `paused`
   frames. The "is this a recordable frame" predicate becomes:

   ```
   frame is not None
   and frame.track_name != ""
   and frame.vehicle_name != ""
   and not frame.paused
   ```

   `read_frame()` already returns `None` when no player slot exists (i.e.
   the sim is in main menu with `mNumVehicles == 0`), so a `None` frame is a
   reliable "not in session" signal. `track_name`/`vehicle_name` empty on a
   non-`None` frame is the loading-screen transition state.

3. **Session lifecycle in the loop.** A *session* is one continuous span
   where `(track_name, vehicle_name)` is constant. Open a `SessionWriter`
   when the first recordable frame arrives. Close it when:
   - track or vehicle changes (and immediately open a new writer for the
     incoming combo), or
   - frames stop arriving for more than 5 s (sim quit to main menu, loading
     screen too long to be a transition, etc.). Close the writer cleanly so
     its sidecar is final; then start a fresh writer when a recordable
     frame next arrives.

   No reconnect-after-sim-crash. If the sim quits, the writer closes; the
   user can Ctrl+C and restart the recorder if they want to switch sims.
   Mid-session sim crashes during a drive are handled by the existing
   orphan-shard recovery on next startup (piece A).

4. **Multi-session overview in `summary`.** `lap-telemetry summary <dir>`
   reads every `session_*.parquet` in the directory, joins each with its
   sidecar, and prints a one-line-per-session table sorted by `started_utc`:

   ```
   started_utc           sim   track                  vehicle                                laps   duration
   --------------------- ----- ---------------------- -------------------------------------- ------ ----------
   2026-05-10T14:02:11Z  lmu   Circuit de Barcelona   DKR Engineering #4:ELMS25                  4      8:31.2
   2026-05-10T14:48:33Z  lmu   Lemans                 Porsche 963                                3     12:04.7
   ```

   `summary <file.parquet>` keeps the existing per-lap behaviour. The same
   command, dispatched on whether the path is a file or a directory.

**What's deliberately out of scope.** Sim-crash auto-reconnect (Ctrl+C and
restart instead). Mid-session paused-frame detection from `mGamePhase`
(low-priority; can be done later as an analysis-time filter). Live status
output during long idle periods (the user explicitly declined this).

---

## Steps

1. **Sector capture.** Edit `Frame` in `connect.py` to add
   `last_sector_1_s`, `last_sector_2_s`. Read from `scor_v.mLast{Sector1,
   Sector2}` in both `LMUConnection.read_frame` and `RF2Connection.read_frame`.
   Map `-1.0` → `float("nan")`.
2. **Schema.** Add the two columns to `_SCHEMA` and `SessionWriter.append` in
   `writer.py`.
3. **Sidecar lifecycle.** Refactor `SessionWriter` to:
   - Track in-progress fields on `self` (`_sidecar_path`, `_row_count`).
   - Write the initial sidecar at the end of `__init__`.
   - Add a private `_write_sidecar(in_progress: bool, recovered: bool = False)`
     helper that does the atomic temp-file swap.
   - Call it from `__init__`, `flush_shard`, and `close`.
4. **Recovery.** Rewrite the sidecar-handling branch in
   `recover_orphaned_shards`:
   - If `<stem>.json` exists, load it, set `recovered: true`,
     `in_progress: false`, recompute `row_count` from `merged.num_rows`,
     recompute `lap_count` from the unique `lap_number` values, leave
     `ended_utc` as it was (or set to `"unknown"` if absent), write back.
   - If `<stem>.json` does not exist, fall back to the current stem-derived
     best effort (track slug, vehicle "unknown") and set `recovered: true`.
5. **Summary display.** Extend `summary.py`:
   - Add an `_HAS_SECTORS` check on schema names.
   - Build a `dict[int, tuple[float, float]]` mapping lap N → (s1, s2) by
     scanning lap boundaries (first frame of lap N+1 supplies lap N's
     splits). Cleanly handle NaN (display `-`).
   - Print the new columns right-aligned, matching the existing format.
6. **Setup-file heuristic (piece C addition).** Snapshot the most-recent
   `.svm` filename in `<sim>/UserData/player/Settings/<track>/` at
   `SessionWriter.__init__` and stamp it into the sidecar as
   `setup_file_guess`. The sim doesn't expose the loaded setup name on SHM,
   so this is a heuristic; the field name signals that. `summary` prints
   `setup  : <filename> (guess)` when populated.
7. **Patient probe (piece D).** Add a retry loop around `probe_and_connect`
   in `record.py`. `--probe-timeout 0` (the new default) means "retry until
   interrupted." SIGINT during the wait returns status 0. `--once` keeps a
   3 s default unless the user passes `--probe-timeout` explicitly.
8. **New frame gate + multi-session lifecycle (piece D).** Replace the
   `not in_realtime or paused` filter in `record.py` with the predicate
   from §D.2. Track `(last_track, last_vehicle)` as before; on change, close
   the existing writer and open a new one. Keep a `last_frame_time`
   timestamp; if more than 5 s elapse without a recordable frame, close the
   writer.
9. **Summary directory mode (piece D).** In `summary.py`, dispatch on
   `path.is_dir()`. Directory branch globs `session_*.parquet`, reads each
   sidecar, and prints the one-line-per-session table from §D.4. File
   branch is unchanged.
10. **Acceptance test** (below).

---

## Backward compatibility

- Old Parquet files (no `last_sector_*` columns): summary prints `-` in the
  three sector columns. No errors.
- Old sidecars (no `in_progress` key): recovery treats them as already-final
  (don't overwrite cleanly-closed sessions). Use `in_progress` as the trigger
  for recovery-time updates.
- Schema version stays `"1"` — adding optional columns is non-breaking. Bump
  to `"2"` only if we ever remove or rename a column.

---

## M3 acceptance test

The recorder is started *before* the sim. The same `lap-telemetry record`
process is expected to span the whole test, with multiple sims-side
sessions during it.

### Step 1 — patient probe

```powershell
lap-telemetry record --out-dir ./sessions
# (LMU not running; recorder should print "waiting for active sim..." and stay alive)
```

Pass criteria:
- Recorder prints a "waiting" line and does not exit.
- Ctrl+C aborts cleanly with status 0.

### Step 2 — first session

Start the recorder, then launch LMU, load into a session, drive 2+ laps,
**stay in the recorder** (do not Ctrl+C yet).

Pass criteria:
- Recorder prints `lap-telemetry: track=… vehicle=…` once frames start
  arriving.
- A `session_*.parquet` + `.json` pair appears in `./sessions/` after the
  first 30 s flush.

### Step 3 — switch car/track within the same recorder run

Without stopping the recorder, return to LMU's main menu and load a
different car or track. Drive 1+ lap on the new combo. Then Ctrl+C the
recorder.

Pass criteria:
- Recorder prints a session-closed line for combo 1 followed by a fresh
  `track=… vehicle=…` line for combo 2.
- Two distinct `session_*.parquet` files now exist, one per combo.
- Each file's sidecar has `in_progress: false`, the correct (different)
  `track` / `vehicle_name`, and matching `started_utc` / `ended_utc`.

### Step 4 — overview

```powershell
lap-telemetry summary ./sessions
```

Pass criteria:
- One line per session, sorted by `started_utc`.
- Columns: started_utc, sim, track, vehicle, laps, duration.
- Both sessions from steps 2–3 appear with the right metadata.

### Step 5 — per-session detail

```powershell
lap-telemetry summary sessions/<combo-1>.parquet
```

Pass criteria (per the original M3 piece A/B/C bar):
- `track`, `vehicle`, `sim`, period times all populated (no `unknown`).
- `setup` line shows a real `.svm` filename.
- Sector columns `s1`, `s2`, `s3` show real times for middle laps and `-`
  for first/last.
- For at least one middle lap, `s1 + s2 + s3 ≈ duration` (within 0.05 s).
- No orphaned `.partN.parquet` files remain.

### Hard-kill recovery (THE point of this milestone)

```powershell
lap-telemetry record --out-dir ./sessions
# drive 1+ complete lap, then HARD KILL the terminal (close window / Stop-Process -Force)
# the .partN.parquet shards plus the in-progress <stem>.json should remain in ./sessions
lap-telemetry record --out-dir ./sessions
# Ctrl+C immediately after the "recovering N orphaned shards" line
lap-telemetry summary sessions/<recovered>.parquet
```

Pass criteria (this is the M3 bar):
- `track` is the **real track string**, not the slug (e.g. `Circuit de Barcelona`,
  not `circuit-de-barcelona`).
- `vehicle` is the **real vehicle name** (e.g. `DKR Engineering #4:ELMS25`),
  not `unknown`.
- `sim` is `lmu` (or `rf2`), not `unknown`.
- `started_utc` is the original session's start time, not the recovery's.
- Sidecar contains `"recovered": true` and `"in_progress": false`.
- Sector columns work the same as in the happy path for the recovered laps.

If any field above shows `unknown`, M3 is not done.
