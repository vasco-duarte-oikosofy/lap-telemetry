# lap-telemetry — Design Spec

Status: **v0.1 — M3 complete, ready for M4** · 2026-05-10

A telemetry recorder + lap-comparison tool for rFactor 2 and Le Mans Ultimate. Reads the same shared memory that TinyPedal reads, writes laps to a standard columnar format, and lets you overlay throttle/brake/speed/RPM/slip traces between two laps to find where time was lost or gained.

### Approved decisions (locked for v0.1)

1. **Storage format: Parquet (Snappy) + JSON sidecar.** Not CSV, not SQLite, not MoTeC `.ld`. Columnar, ~10× smaller than CSV, universally readable.
2. **Separate process from TinyPedal.** Recorder and analyzer are standalone; SHM submodules are re-vendored from the same upstreams TinyPedal uses. No edits to TinyPedal's code or data folders.
3. **Fixed 50 Hz sample rate.** Sim ticks ~90–100 Hz; we deliberately downsample. Configurable via `--rate` but 50 Hz is the canonical default.
4. **Distance-aligned comparison only.** Time-aligned alignment is deferred past v0.1.

---

## 1. Goals

1. **Record** a session's telemetry (player vehicle only) at high rate while a sim is running, with zero in-game configuration beyond the existing TinyPedal/rF2-SHM plugin setup.
2. **Store** each session in a single, self-describing, language-agnostic file (Parquet) plus a small JSON sidecar for metadata.
3. **Compare** any two laps from any two sessions on a single chart: traces aligned to lap distance (not time), with a delta-time-vs-distance trace driven by speed integration. Picks out the corner where lap A loses to lap B.
4. **Stay out of TinyPedal's way.** Run as a separate process; no changes to TinyPedal's code, no writes inside its data folders.

## 2. Non-goals

- Live HUD / overlay rendering. TinyPedal already does that.
- Multi-vehicle / opponent telemetry. Player car only.
- Setup/garage analysis, weather, tyre strategy modelling. Out of scope.
- MoTeC `.ld` export. Proprietary; revisit only if a user asks.
- Network/cloud sync. Files are local.

## 3. Constraints from the data source

Pulled from the `pyRfactor2SharedMemory` and `pyLMUSharedMemory` modules that TinyPedal vendors as submodules:

- Shared memory updates run roughly at the sim's physics tick (~90–100 Hz for rF2/LMU). We poll on a fixed interval.
- A `paused` flag in scoring info goes high when the game freezes (menu, pause). We must not record paused frames — or we'll get long flat segments that pollute lap detection.
- `mInRealtime` is **not** a useful "is the player driving" gate. It is False during pit-garage UI, menu screens, and inter-session transitions — i.e., a meaningful fraction of any normal driving evening. The reliable "in session" signal is `read_frame() != None` (the player slot exists, i.e. `mNumVehicles > 0` and `mIsPlayer` is set somewhere) combined with non-empty `track_name` and `vehicle_name`. (M3 first live test confirmed this — a 2-lap drive with the old gate produced zero output.)
- Vehicle data lives in an array indexed by slot; the player's slot ID can change. Re-resolve the local-player index every frame via the scoring section.
- Strings (track name, vehicle class) come back as bytes; tyre temps in Kelvin. Convert at the recorder boundary, not in analysis code. String decoding is UTF-8 with a latin-1 fallback for legacy mod content; hardcoded for v0.1, made configurable only if a user reports mojibake.
- TinyPedal's own files in `deltabest/`, `trackmap/`, `pacenotes/` etc. use specific extensions (`.csv`, `.sector`, `.fuel`, `.energy`, `.svg`). We will not write any of those extensions in any TinyPedal-adjacent folder.

## 4. Architecture

Two processes, one shared file format:

```
   ┌───────────────────────────┐         ┌───────────────────────────┐
   │  recorder (CLI)           │  files  │  analyzer (CLI / GUI)     │
   │  ─ polls SHM @ ~50 Hz     │ ───────▶│  ─ loads Parquet sessions │
   │  ─ detects lap boundaries │         │  ─ overlays 2 laps        │
   │  ─ writes session.parquet │         │  ─ computes Δt(distance)  │
   └───────────────────────────┘         └───────────────────────────┘
```

Both are plain Python packages in this repo. The recorder depends on `pyRfactor2SharedMemory` and `pyLMUSharedMemory` (vendored as git submodules from the TinyPedal forks — same upstreams TinyPedal uses, so we get the same parity). The analyzer depends only on the file format.

### 4.1 Recorder

- Designed to be started *before* the sim and left running across the whole driving evening. The probe retries until a sim shows up; `--probe-timeout 0` (the default) means "wait until interrupted."
- Connects to whichever sim becomes active first (LMU first, fall back to rF2). Same probe order TinyPedal uses.
- mmap access mode: M1 used direct access (read-through, no buffer copy) since print-a-frame can tolerate occasional tearing. M2 switched to copy access with the writer's version-block check, so a recorded row never spans two sim ticks.
- Polls at a fixed 50 Hz wall-clock interval (configurable). Sim updates faster; we deliberately downsample to keep files reasonable. 50 Hz × 2 hours ≈ 360k rows — fine for Parquet.
- Each frame:
  1. Read scoring + player telemetry slot in one pass.
  2. Drop the frame if `paused`, if `read_frame()` returned None, if `track_name` or `vehicle_name` is empty, or if `mDeltaTime == 0` (duplicate). `mInRealtime` is *not* used as a gate (see §3).
  3. Append a row to an in-memory buffer, keyed by `(session_id, lap_number, lap_distance, session_time)`.
- Every N seconds (default 30) flush the buffer to a temp Parquet shard, and refresh the JSON sidecar in place (`in_progress: true`, latest row/lap counts). On graceful shutdown (or session change), concatenate shards into the final session file. This protects against crashes losing the whole stint, and ensures hard-killed sessions have an identifying sidecar on disk for orphan-recovery to stamp.
- Lap boundaries are detected by monotonic increase of `mLapNumber`. We do *not* trust lap distance wraparound alone — the sim sometimes reports it before the lap counter ticks.
- **Multi-session per recorder run.** Emits one session file per `(track, vehicle)` combo. The combo changing closes the current writer and opens a new one. If recordable frames stop arriving for more than 5 s (sim quit to main menu, loading screen overshoot, etc.), the writer is closed cleanly; a fresh writer opens on the next recordable frame.

### 4.2 Analyzer

Two entry points, sharing one core:

- `lap-telemetry summary <session.parquet>` — print a table of laps with lap time, sectors, valid flag.
- `lap-telemetry summary <dir>` — one-line-per-session overview of every `session_*.parquet` in the directory: started_utc, sim, track, vehicle, laps, duration. Sorted by `started_utc`.
- `lap-telemetry compare <ref.parquet>:<lap_n> <cmp.parquet>:<lap_m>` — open a window with overlaid traces.

The viewer uses **PyQtGraph** (fast, mouse-pannable, plays nicely with PySide2 which is already on the system from TinyPedal). Layout: vertical stack of linked plots — speed, throttle/brake, RPM/gear, steering, slip angle (per axle), Δt — all on a shared lap-distance x-axis with a synced cursor.

Δt is computed by integrating `1/speed` over distance for each lap and subtracting. Distance bins are 1 m by default; we resample both laps onto the same bin grid before subtracting.

## 5. File format

### 5.1 Session file: `session_<utc>_<track>_<class>.parquet`

One row per recorded frame. Parquet (Snappy compression) chosen because:
- Columnar — analyzer can read just the channels it plots without paying for the rest.
- Self-describing schema with dtypes; no string-parsing footguns.
- Universally consumable: pandas, polars, duckdb, R, Julia, Rust, browser via parquet-wasm. That's the "standard format" requirement.

Columns (units in the name, no ambiguity):

| Column | Type | Notes |
|---|---|---|
| `session_time_s` | f64 | `mElapsedTime` from scoring |
| `lap_number` | i32 | from `mLapNumber` |
| `lap_distance_m` | f32 | distance along centerline |
| `lap_time_s` | f32 | `session_time_s - mLapStartET` |
| `speed_kph` | f32 | from `mLocalVel.z` (or magnitude) |
| `throttle_norm` | f32 | 0..1, unfiltered |
| `brake_norm` | f32 | 0..1, unfiltered |
| `clutch_norm` | f32 | 0..1, unfiltered |
| `steering_norm` | f32 | -1..1, unfiltered |
| `gear` | i8 | -1=R, 0=N |
| `engine_rpm` | f32 | |
| `pos_x_m`, `pos_y_m`, `pos_z_m` | f32 | world position |
| `slip_ratio_fl/fr/rl/rr` | f32 | computed from patch velocities |
| `slip_angle_fl/fr/rl/rr_deg` | f32 | computed |
| `tire_temp_fl_c` … (×4, ×3 zones) | f32 | Kelvin → °C at boundary |
| `tire_pressure_fl_kpa` … (×4) | f32 | |
| `brake_temp_fl_c` … (×4) | f32 | Kelvin → °C |
| `suspension_deflection_fl_m` … (×4) | f32 | |
| `tire_load_fl_n` … (×4) | f32 | |
| `lap_invalidated` | bool | LMU-only; false on rF2 |
| `abs_active`, `tc_active` | bool | LMU-only; null on rF2 |

The lap layer (one row per lap, derived) is *not* materialized in the file — the analyzer derives it by groupby on `lap_number`. Keeps the recorder simple.

### 5.2 Sidecar: `session_<utc>_<track>_<class>.json`

Small JSON written next to the Parquet, holding fields that don't make sense as columns:

```json
{
  "schema_version": "1",
  "recorder_version": "0.1.0",
  "started_utc": "2026-05-09T17:55:11Z",
  "ended_utc": "2026-05-09T18:42:03Z",
  "sim": "lmu",
  "track": "Bahrain International Circuit",
  "track_length_m": 5412.0,
  "vehicle_class": "GT3",
  "vehicle_model": "...",
  "sample_rate_hz": 50,
  "row_count": 187234,
  "lap_count": 23
}
```

## 6. CLI surface

```
lap-telemetry record [--rate 50] [--out-dir ./sessions] [--probe-timeout 0]
lap-telemetry summary ./sessions/<file>.parquet         # per-lap detail of one session
lap-telemetry summary ./sessions                        # one line per session file
lap-telemetry compare ./sessions/A.parquet:7 ./sessions/B.parquet:3
lap-telemetry export ./sessions/A.parquet --to csv      # for sharing
```

`--probe-timeout 0` (the default) means "wait forever for a sim, Ctrl+C to abort." A positive value bounds the wait — useful for `--once` smoke tests, where it defaults to 3 s.

That's the whole thing. No config file in v0.1 — flags only.

## 7. Phasing

- **M1 — recorder skeleton. ✅ done 2026-05-09.** Submodule the SHM libs, connect, print a frame, exit cleanly on Ctrl+C. Verified against a live LMU session (Bahrain, GT3) — same SHM regions TinyPedal reads.
- **M2 — write loop. ✅ done 2026-05-10.** Buffer → Parquet shards → final session file + JSON sidecar; lap-boundary detection; copy-mode mmap; orphaned-shard recovery on next startup. `lap-telemetry summary` prints a per-lap overview (frames, duration, valid). Acceptance test passed at Circuit de Barcelona, 4-lap LMU session, 26,893 rows @ 50 Hz.
- **M3 — read path: sectors + recoverable metadata + patient multi-session recorder. ✅ done 2026-05-10.** Capture sector splits per lap and display them in `summary`. Sidecar metadata (`track`, `vehicle_name`, `setup_file_guess`) survives a hard kill: written at session start, refreshed on every shard flush, finalised at close; orphan recovery preserves the in-progress sidecar instead of guessing from the filename stem. Recorder retries the probe until a sim appears, drops the broken `mInRealtime` gate, and rotates session files automatically when the user changes car/track or quits to the main menu — one recorder run spans an entire driving evening of mixed sessions. `summary <dir>` summarises all sessions in a directory; `summary <file>` iterates per chronological segment so race-restart `lap_number` rewinds and rolling-start frames render in the order they were driven. Acceptance test passed at Circuit de Barcelona — recovery from a hard-killed 7-lap session restored real `track` / `vehicle` / `setup_file_guess` metadata, and a follow-up 6-lap session displayed sectors summing to lap duration to within rounding. Two SHM-timing artifacts left for future cleanup (see §10).
- **M4 — `compare` command, single-plot.** Overlay just speed-vs-distance for two laps. Validates resampling.
- **M5 — full plot stack.** Add throttle/brake, RPM/gear, steering, slip, Δt panel.
- **M6 — quality of life.** Lap filtering (in/out laps, invalid), sector splits, persistent zoom.

Each milestone ends in a runnable build. We don't move to the next until the previous demos end-to-end.

## 8. Open questions

1. **Slip angle definition.** We can compute it from `mLateralPatchVel / mLongitudinalPatchVel` per wheel, but TinyPedal's `wheels` module already does this; worth diffing against its formula to make sure we're consistent with what the user is used to seeing.
2. **Lap invalidation on rF2.** rF2 telemetry doesn't expose `mLapInvalidated` directly — we'd need to derive it from track-cut warnings or skip the column. Default: leave null on rF2; revisit if it matters.
3. **Naming.** `lap-telemetry` is a placeholder. If a better name emerges, rename while there are still no external consumers.

### Resolved

- **Speed source** (resolved 2026-05-09, M1). Use magnitude `‖mLocalVel‖`, not `mLocalVel.z`. Rationale: during yaw the car is moving sideways too, and `.z` understates true ground speed in slides and tight corners — exactly the moments we care about when comparing laps. Cost is one extra multiply + sqrt per frame, negligible.

## 9. Out-of-scope but worth noting

- Could ingest TinyPedal's existing `.csv` deltabest files for a one-shot "compare my new lap to my best" mode without recording from scratch. Easy win for M3+.
- Could publish frames over a local WebSocket so a browser-based viewer is feasible without bundling Qt. Defer until someone asks.

## 10. Known issues / future fixes

Surfaced by the M3 live test (Circuit de Barcelona, LMP3, 2026-05-10). Both fixes live in the **reader** (`summary.py` and any future analysis layer), not the recorder — the recorder is faithful; the SHM is the one acting up.

### O1. Sector lookup catches `mLastSector*` mid-update

**Symptom.** A clean middle lap displays `-` for S1/S2/S3 in `summary` even though it has `valid: yes` and a real `lap_time_s`. Observed on lap 3 of the Barcelona run: laps 4 and 5 surrounding it had real splits, lap 3 was empty.

**Cause.** The reader takes `(s1, cum_s2)` from the *first frame* of the next chronological segment, on the principle that `mLastSector*` carries the previously-completed lap's splits. But on some boundaries the very first post-line frame catches the SHM mid-update — `mLastSector1` is 0 (the sim's reset state during the transition tick) before being populated with the real value 1–2 ticks later. The `s1 > 0 and cum_s2 > s1` filter (added to reject Restart-Session zeros) then treats the lap as having no sector data.

**Fix.** Sample `mLastSector*` from a frame *inside* the next segment, not the literal first frame. Walk forward until both values are positive and `cum_s2 > s1`, capped at e.g. 25 frames (~0.5 s at 50 Hz). That wins back the dropped laps without making the filter looser for actual reset cases.

### O2. Apparent off-by-one in `mLastSector*` between consecutive laps

**Symptom.** Two consecutive laps display identical S1 and S2 to the millisecond while their total durations differ. Observed on laps 4 (1:37.842) and 5 (1:37.834) of the Barcelona run — both rendered as `s1=29.375, s2=39.034`, with the 8 ms gap absorbed entirely into S3.

**Cause.** Suspected, not yet confirmed. The most plausible explanation is the same SHM-update lag as O1, applied one lap deeper: when the reader samples the first frame of lap N+1, the `mLastSector*` values it reads still reflect lap N–1, not lap N. The displayed splits would then be shifted by one lap, so "lap 4's S1" is actually lap 3's S1, "lap 5's S1" is actually lap 4's S1, and lap 3 (whose source frame is even further behind) gets the zeros from O1 and renders as `-`. That story is consistent with all the observed data, but it needs a controlled test.

**Fix proposal (paired with O1).** The same "sample inside the next segment" change should also resolve O2 — by waiting for the SHM to settle, the reader gets the just-completed lap's splits rather than a stale carry-over. Worth a debug pass that dumps the first ~10 frames of each segment's `mLastSector*` to confirm the timing model before changing the lookup.

### Status

Not blocking M3 acceptance — sector display works for the well-behaved case (laps 2, 4, 5 in the live run had real, plausible splits summing to the lap duration). Slot for M3.5 polish or a deliberate M4 sub-task.
