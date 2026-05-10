# lap-telemetry — Claude Code context

See [SETUP.md](SETUP.md) for environment setup (venv, pip install, verify).

See [DESIGN.md](DESIGN.md) for architecture, file format, and milestone plan.

See [m2-plan.md](m2-plan.md) for the M2 implementation plan (write loop, Parquet shards, sidecar).

## Current state

M1 complete. Recorder skeleton connects to LMU or rF2 via shared memory, prints
one frame per poll tick, exits cleanly on Ctrl+C. No Parquet writing yet (M2).

## Key facts

- Entry point: `lap_telemetry/cli.py` → dispatches to `lap_telemetry/recorder/record.py`
- SHM abstraction: `lap_telemetry/recorder/connect.py` — wraps both sims behind a
  common `Frame` dataclass and `probe_and_connect()` function
- Submodules `pyRfactor2SharedMemory` and `pyLMUSharedMemory` are injected into
  `sys.path` by `connect.py`; do not add them as pip dependencies
- M1 uses direct mmap access (no copy). M2 must switch to copy mode before writing rows

## Commands

```powershell
lap-telemetry record           # stream frames at 50 Hz, Ctrl+C to stop
lap-telemetry record --once    # print one frame and exit (good for smoke-testing)
lap-telemetry record --rate 25 # override poll rate
```
