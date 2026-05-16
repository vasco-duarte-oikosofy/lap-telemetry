# Development Setup

## Prerequisites

- Python 3.10 or later
- Git (with submodule support)
- Le Mans Ultimate **or** rFactor 2 installed with the rF2 shared-memory plugin loaded
  (the same plugin TinyPedal requires — if TinyPedal works, this will too)

## First-time setup

```powershell
git clone --recurse-submodules <repo-url>
cd lap-telemetry
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

If you cloned without `--recurse-submodules`, populate the submodules first:

```powershell
git submodule update --init
```

## Verify the install

With the sim running, in or out of a session:

```powershell
lap-telemetry record --once
```

`--once` uses a bounded 3 s probe so it fails fast if the sim isn't up. The
plain `lap-telemetry record` waits forever for the sim — start it before
launching LMU and it will pick up automatically.

Expected output (values will differ):

```
lap-telemetry: probing for active sim (timeout 3.0s)...
lap-telemetry: connected to lmu (Ctrl+C to stop)
lap-telemetry: track=Bahrain International Circuit vehicle=BMW M4 GT3
lap-telemetry: lap boundary -> lap 3
sim=lmu t=  342.18s lap=  3 dist=  812.4m lap_t= 18.43s v= 187.3kph thr=0.94 brk=0.00 str=-0.03 gear= 5 rpm=  7821 realtime=1 idx=0
lap-telemetry: stopped. frames=1 skipped=0
```

If the sim is not running you will get a `ConnectError` — start the sim first.

## Day-to-day

Activate the venv before working:

```powershell
.venv\Scripts\activate
```

Run the recorder continuously (Ctrl+C to stop):

```powershell
lap-telemetry record
```

## Submodules

`vendor/pyRfactor2SharedMemory` and `vendor/pyLMUSharedMemory` are vendored as git submodules.
They are added to `sys.path` automatically by `connect.py` — no separate `pip install` step is needed for them.
