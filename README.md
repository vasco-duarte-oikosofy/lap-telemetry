# lap-telemetry

Telemetry recorder + lap-comparison tool for rFactor 2 and Le Mans Ultimate.

See [DESIGN.md](DESIGN.md) for the full spec.

## Status

**M1 — recorder skeleton.** Reads the same shared memory TinyPedal reads, prints one frame, exits cleanly on Ctrl+C.

## Setup

```
git clone --recurse-submodules <this repo>
cd lap-telemetry
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -e .
```

If you cloned without `--recurse-submodules`:

```
git submodule update --init
```

## Usage (M1)

Sim must be running with the rF2/LMU shared-memory plugin loaded (same one TinyPedal uses).

```
lap-telemetry record           # connect, print one frame per ~20 ms, Ctrl+C to stop
lap-telemetry record --once    # print exactly one frame, exit
lap-telemetry record --rate 25 # override poll rate
```
