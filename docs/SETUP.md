# Development Setup

## Prerequisites

- Python 3.10 or later
- Node.js 20 or later (the test suite and the standalone build run on Node;
  Node 22 is what CI/laptops are validated on)
- Git (with submodule support)
- Le Mans Ultimate **or** rFactor 2 installed with the rF2 shared-memory plugin loaded
  (the same plugin TinyPedal requires — if TinyPedal works, this will too)

## Platform support at a glance

| Capability | Windows | macOS | Linux |
|---|---|---|---|
| `lap-telemetry record` (live sim capture) | ✅ | ❌ shared-memory plugin is Windows-only | ❌ |
| Reference/model/outline tooling, coach CLI, TTS | ✅ | ✅ | ✅ |
| Test suite (`bash scripts/test-summary.sh`) | ✅ | ✅ | ✅ |
| Standalone build (`npm run build`) | ✅ | ✅ | ✅ |
| TinyPedal turn-label export + widget QA | ✅ | ✅ (needs the sibling `tinypedal` checkout) | ✅ |

Everything except **live recording** is platform-neutral. Recording needs the
sim, and the sim is Windows-only, so on macOS you work with committed recordings
and fixtures (`product/data/`, `sessions/`) rather than capturing new ones.

## First-time setup (Windows, PowerShell)

```powershell
git clone --recurse-submodules <repo-url>
cd lap-telemetry
python -m venv .venv
.venv\Scripts\activate
pip install -e .
npm install
```

## First-time setup (macOS / Linux)

```bash
git clone --recurse-submodules <repo-url>
cd lap-telemetry
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
npm install
npx playwright install chromium   # only needed for the Playwright UI tests
```

Notes for macOS:

- Use `python3`; there is no `python` on a stock macOS install. The Node test
  wrappers do not care — they resolve the interpreter themselves through
  `dev/scripts/python.js` (`docs/TESTING_LESSONS.md` L16), preferring this repo's
  `.venv` and falling back to `python3` on `PATH`. So `bash
  scripts/test-summary.sh` works without activating the venv, as long as the
  interpreter it picks has the dependencies (the venv does, a bare system
  `python3` usually does not).
- The coach LLM/TTS extras (`openai`, `litellm`, `kokoro-onnx`, `sounddevice`)
  install on macOS; `sounddevice` needs PortAudio (`brew install portaudio`).
- The TinyPedal Qt widget QA runs only if a sibling `../tinypedal` checkout with
  `.venv/bin/python` exists; otherwise that check reports `[SKIP]` and the
  track-only export regression still runs.

If you cloned without `--recurse-submodules`, populate the submodules first:

```bash
git submodule update --init
```

## Verify the install

```bash
bash scripts/test-summary.sh        # full fast suite (add --pw for browser tests)
npm run build                       # regenerates product/dist/compare.html
```

Then, on Windows with the sim running, in or out of a session:

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
.venv\Scripts\activate     # Windows
```

```bash
source .venv/bin/activate  # macOS / Linux
```

Run the recorder continuously (Ctrl+C to stop; Windows only):

```powershell
lap-telemetry record
```

## Submodules

`vendor/pyRfactor2SharedMemory` and `vendor/pyLMUSharedMemory` are vendored as git submodules.
They are added to `sys.path` automatically by `connect.py` — no separate `pip install` step is needed for them.
