# lap-telemetry — Claude Code context

See [SETUP.md](SETUP.md) for environment setup (venv, pip install, verify).

See [DESIGN.md](DESIGN.md) for architecture, file format, and milestone plan.

See [m2-plan.md](m2-plan.md) for the M2 implementation plan (write loop, Parquet shards, sidecar).

See [m3-plan.md](m3-plan.md) for the M3 implementation plan (sectors in summary, recoverable sidecar metadata).

## Current state

M3 in progress. `lap-telemetry record` is a long-running daemon — start it
before the sim and leave it running across an evening of mixed sessions. The
probe retries until LMU/rF2 appears (`--probe-timeout 0` = forever). The
frame gate ignores the broken `mInRealtime` flag; recordable = non-None
frame with non-empty track + vehicle and not paused. One session file is
written per `(track, vehicle)` combo; combo changes (or 5 s of idle) close
the writer cleanly and start a fresh one on the next recordable frame.

`SessionWriter` writes the JSON sidecar at session start, refreshes it on
every shard flush, and finalises it at close — so a hard kill still leaves
identifying metadata on disk. Orphan recovery on next startup stamps
`recovered: true` and recomputes counts. Sidecar also carries a
heuristic `setup_file_guess` (the most-recently-modified `.svm` in the
sim's per-track Settings folder).

Parquet schema includes `last_sector_1_s` / `last_sector_2_s`, sourced from
`scor_v.mLastSector{1,2}` (sim's `-1.0` "not set" sentinel mapped to NaN).
`lap-telemetry summary <file>` shows S1/S2/S3 per lap (S3 derived from
duration); `lap-telemetry summary <dir>` prints one line per session in the
directory.

## Key facts

- Entry point: `lap_telemetry/cli.py` → dispatches to `lap_telemetry/recorder/record.py`
- SHM abstraction: `lap_telemetry/recorder/connect.py` — wraps both sims behind a
  common `Frame` dataclass and `probe_and_connect()` function
- Writer: `lap_telemetry/recorder/writer.py` — `SessionWriter` owns buffering,
  shard files, finalisation, and sidecar; module-level `PARQUET_SCHEMA` constant
- Submodules `pyRfactor2SharedMemory` and `pyLMUSharedMemory` are injected into
  `sys.path` by `connect.py`; do not add them as pip dependencies
- Copy-mode mmap (`create(0)`) is required when writing rows — direct mode can tear

## Commands

```powershell
lap-telemetry record                        # waits for sim, records until Ctrl+C
lap-telemetry record --out-dir ./sessions   # explicit output dir
lap-telemetry record --once                 # 3 s probe, print one frame, exit
lap-telemetry record --rate 25              # override poll rate
lap-telemetry record --probe-timeout 5      # bound the wait (0 = forever, default)
lap-telemetry summary <file>.parquet        # per-lap overview of one session
lap-telemetry summary <dir>                 # one-line overview across a folder
```
