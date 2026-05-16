# lap-telemetry

Telemetry recorder + browser-based lap-comparison tool for **rFactor 2** and **Le Mans Ultimate**.

Reads the same shared memory that [TinyPedal](https://github.com/s-victor/TinyPedal) reads, writes laps as standard Parquet + JSON sidecar, and gives you an offline HTML viewer to overlay any two laps and find where time was lost or gained.

- **Recorder**: long-running CLI daemon, 50 Hz, captures `speed`, `throttle`, `brake`, `RPM`, `gear`, `steering`, `slip angle` (per axle), `ABS/TC` activity (LMU), per-frame position and lap distance.
- **Comparison app**: a browser app under `product/web/`, bundled to `product/dist/compare.html` for standalone `file://` use. Drop in two parquet files (or a recording vs a TinyPedal `deltabest.csv`) and you get 8 panels + circuit map with synced cursor, drag-zoom, sector markers, and a smooth Δt trace.

See [`DESIGN.md`](DESIGN.md) for the full spec and rationale.

## Status

**v0.1** — M1–M6 + F1–F4 shipped. Daily-driven by the author across LMU sessions on Bahrain, Barcelona, Spa, and Le Mans.

## Quick start

### Prerequisites

- Python 3.10+
- Le Mans Ultimate **or** rFactor 2 with the rF2 shared-memory plugin loaded (same plugin TinyPedal requires).
- Modern browser (Chrome / Edge / Firefox) for the comparison app.

### Install

```powershell
git clone --recurse-submodules https://github.com/vasco-duarte-oikosofy/lap-telemetry.git
cd lap-telemetry
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

`pyRfactor2SharedMemory` and `pyLMUSharedMemory` come in as git submodules — they're injected into `sys.path` at runtime, no separate install.

If you forgot `--recurse-submodules`:

```powershell
git submodule update --init
```

Full setup walkthrough: [`SETUP.md`](SETUP.md).

### Record

```powershell
lap-telemetry record                       # waits for sim, records until Ctrl+C
lap-telemetry record --out-dir ./sessions  # explicit output dir
lap-telemetry record --once                # 3 s probe, print one frame, exit
lap-telemetry record --rate 25             # override poll rate
```

Start it before launching the sim and leave it running across an evening of mixed sessions — combo changes (track or vehicle) or 5 s of idle automatically close the writer and start a fresh file. A hard kill still leaves identifying metadata on disk, and orphan recovery on next startup stamps `recovered: true`.

### Summarize

```powershell
lap-telemetry summary <file>.parquet       # per-lap overview of one session
lap-telemetry summary <dir>                # one-line overview across a folder
```

### Compare

Open `product/dist/compare.html` in a browser — `file://` works, no server needed:

```powershell
npm run build
start product/dist/compare.html
```

Drop one or more `session_*.parquet` files (and their `.json` sidecars) onto the loader, pick a session lap and a reference lap, hit Compare. TinyPedal `deltabest.csv` files load as a synthetic single-lap reference if you want to compare against your TinyPedal best.

## What you see

8 stacked panels on a shared lap-distance x-axis, with a synced cursor and tooltip:

- Speed (km/h), Throttle, Brake, RPM, Gear, Steering, Slip angle (per axle)
- **Δt (ms)** — instantaneous time delta, read directly from each lap's `lap_time_s` column (not integrated 1/speed — see [the Δt RCA](rca-deltat-phantom-error.md) for why this matters)

Plus a circuit-map sidebar (outline / speed-heatmap / brake-heatmap / throttle-heatmap), drag-to-zoom, persistent zoom + lap-colour customisation in `localStorage`, ABS/TC activity strips at the bottom of the brake and throttle panels, and per-sector Δt readouts.

## Repo layout

```
product/
  python/lap_telemetry/
    cli.py             # entry point: `lap-telemetry record` / `summary`
    recorder/
      connect.py       # SHM abstraction over rF2 / LMU, common `Frame` dataclass
      writer.py        # SessionWriter — buffering, Parquet shards, JSON sidecar
      record.py        # daemon loop + lap-boundary detection
  web/
    compare.html       # browser app source
  dist/
    compare.html       # bundled standalone viewer
dev/
  scripts/             # test/build/data-prep implementation scripts
  sessions/            # tracked development session data
pyRfactor2SharedMemory/  # submodule
pyLMUSharedMemory/       # submodule
```

## File format

One parquet file per `(track, vehicle)` session, one row per recorded frame. Columns are dimensioned in the name (`speed_kph`, `lap_distance_m`, `lap_time_s`, …) — no unit ambiguity. JSON sidecar carries `sim`, `track_name`, `vehicle_name`, `setup_file_guess` (best-effort, from the most-recently-modified `.svm`), `started_utc`, `row_count`, `lap_count`.

Parquet works out of the box with pandas, polars, duckdb, R, Julia, Rust, and JS via [hyparquet](https://github.com/hyparam/hyparquet) (which is what the browser app uses).

## Tests

Playwright + Chromium, pre-installed via the dev deps:

```powershell
bash scripts/test-summary.sh                 # full suite, concise output
node dev/scripts/test_m5.js                  # core load/compare + Δt cross-check vs Python
node dev/scripts/test_f1f2.js                # circuit map + zoom
node dev/scripts/test_m6.js                  # lap colours, ABS/TC, deltabest CSV
node dev/scripts/test_m6_extras.js           # heatmaps, sector readouts, persistent zoom
```

Each suite emits a `*-test-report/` folder with screenshots, console log, and a `REPORT.md`.

## Acknowledgments

- **[TinyPedal](https://github.com/s-victor/TinyPedal)** — the in-game HUD that opened the door to LMU shared-memory access for the wider community.
- **[pyRfactor2SharedMemory](https://github.com/TonyWhitley/pyRfactor2SharedMemory)** and **[pyLMUSharedMemory](https://github.com/SimRacingTools/pyLMUSharedMemory)** — the SHM bindings, vendored as submodules.
- **[hyparquet](https://github.com/hyparam/hyparquet)** — pure-JS Parquet reader; the comparison app would not be a single HTML file without it.

## Licence

[MIT](LICENSE) — © 2026 Vasco Duarte.
