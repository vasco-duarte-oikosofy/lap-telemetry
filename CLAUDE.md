# lap-telemetry — Claude Code context

See [SETUP.md](SETUP.md) for environment setup (venv, pip install, verify).

See [DESIGN.md](DESIGN.md) for architecture, file format, and milestone plan.

See [m2-plan.md](m2-plan.md) for the M2 implementation plan (write loop, Parquet shards, sidecar).

## Current state

M2 complete. `lap-telemetry record` streams frames at 50 Hz from LMU or rF2,
buffers them in `SessionWriter`, flushes Parquet shards every 30 s, and on clean
shutdown merges shards into a final `<session>.parquet` + `<session>.json`
sidecar. Orphaned shards from a prior crash are recovered on the next startup.
`lap-telemetry summary <file>` prints per-lap frame counts, durations, and
validity. Acceptance test passed on 2026-05-10 with a 4-lap LMU session at
Circuit de Barcelona (26,893 rows / 537.9 s @ 50.0 Hz, laps 1–3 valid).

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
lap-telemetry record                        # record to ./sessions, Ctrl+C to stop
lap-telemetry record --out-dir ./sessions   # explicit output dir
lap-telemetry record --once                 # print one frame and exit (smoke test)
lap-telemetry record --rate 25              # override poll rate
lap-telemetry summary <file>.parquet        # per-lap overview of a recorded session
```
