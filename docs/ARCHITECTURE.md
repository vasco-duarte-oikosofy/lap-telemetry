# lap-telemetry — High-Level Architecture

> Companion to [DESIGN.md](DESIGN.md) (spec, decisions, phasing) and [RENDER_DESIGN.md](RENDER_DESIGN.md) (rendering pipeline deep-dive).

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   SIM  (rFactor 2  or  Le Mans Ultimate)                                    │
│   └── Shared-memory plugin writes scoring + telemetry structs every tick   │
│                                                                             │
│        ┌──────────────────────────────┐    ┌──────────────────────────────┐ │
│        │  pyLMUSharedMemory           │    │  pyRfactor2SharedMemory      │ │
│        │  (vendored git submodule)    │    │  (vendored git submodule)    │ │
│        └──────────────┬───────────────┘    └──────────────┬───────────────┘ │
│                       │ mmap read                             mmap read    │
│                       ▼                                    ▼               │
│        ┌────────────────────────────────────────────────────────────────┐  │
│        │                    RECORDER  (Python CLI)                       │  │
│        │  lap_telemetry/recorder/                                        │  │
│        │    connect.py   ── probe sim → sim-agnostic Frame dataclass    │  │
│        │    record.py    ── poll loop, lap detection, session rotation  │  │
│        │    writer.py    ── buffer → Parquet shards → final file        │  │
│        │                                                                 │  │
│        │  Output:  session_<utc>_<track>_<sim>.parquet  (+ .json)       │  │
│        │  Rate:    50 Hz wall-clock poll  (downsampled from ~90 Hz sim)  │  │
│        └────────────────────────────────────────────────────────────────┘  │
│                                    │                                       │
│                     files (Parquet + JSON sidecar)                         │
│                                    │                                       │
│                                    ▼                                       │
│        ┌────────────────────────────────────────────────────────────────┐  │
│        │                  ANALYSIS TOOLS                                   │  │
│        │                                                                 │  │
│        │  CLI   lap-telemetry summary <file|dir>                           │  │
│        │        lap_telemetry/summary.py ─ per-lap table, sectors, valid  │  │
│        │                                                                 │  │
│        │  GUI   web/compare.html  (single-file, no server)                 │  │
│        │        ─ load .parquet via parquet-wasm in the browser            │  │
│        │        ─ pick two laps, resample to 1 m bins                      │  │
│        │        ─ overlay traces: speed, throttle, brake, RPM, …         │  │
│        │        ─ Δt(distance) computed directly from lap_time_s           │  │
│        │        ─ circuit map, zoom, hover cursor, drag-reorder panels    │  │
│        └────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Recorder — `lap_telemetry/recorder/`

Designed to be started *before* the sim and left running across a whole driving evening.

| File | Role |
|------|------|
| `connect.py` | Sim probe (LMU first, rF2 fallback). Thin mmap wrapper that reads scoring + telemetry structs and emits a sim-agnostic `Frame` dataclass. Includes speed-integrated distance estimation (F4) to raise `lap_distance_m` resolution from ~3 Hz to 50 Hz. |
| `record.py` | Main poll loop. Retries probe until a sim appears; drops `paused`/empty frames; detects lap boundaries via `mLapNumber` monotonic increase; rotates session files on track/vehicle change; flushes in-memory buffer to Parquet shards every 30 s. |
| `writer.py` | `SessionWriter` — append `Frame` rows to a typed PyArrow buffer, flush shards with Snappy compression, concatenate on close, and write/update a JSON sidecar next to the Parquet. `recover_orphaned_shards()` merges `.partN.parquet` files left by a hard kill. |

**Key design decisions**
- **No `mInRealtime` gate** — it is False in LMU's pit garage and menus. We use "frame is non-None + track/vehicle non-empty + not paused" instead.
- **Speed-integrated distance** — `mLapDist` updates at scoring rate (~3–4 Hz). We integrate `‖mLocalVel‖` between anchor ticks so every 50 Hz frame has a sub-metre distance estimate.
- **Shard + sidecar from start** — a hard kill still leaves recoverable metadata on disk.
- **Multi-session per run** — changing car or track closes the current writer and opens a new one automatically.

---

### 2. CLI — `lap_telemetry/cli.py`

Entry point:

```
lap-telemetry record [--rate 50] [--out-dir ./sessions] [--probe-timeout 0]
lap-telemetry summary <session.parquet>      # per-lap detail
lap-telemetry summary <dir>                  # one line per session file
```

No config file in v0.1 — flags only.

---

### 3. Summary tool — `lap_telemetry/summary.py`

Reads a Parquet (or scans a directory) and prints a human-readable table.

- Iterates per **segment** (contiguous run of constant `lap_number`) rather than per unique lap number. This correctly handles race-restart rewinds and rolling-start out-laps.
- Sector lookups walk up to 25 frames into the next segment to avoid catching SHM mid-update (O1/O2 fix, see DESIGN.md §10).
- First and last segments are marked incomplete (dash-out) regardless of duration.

---

### 4. Comparison App — `web/compare.html` + `web/js/*.js` + `web/css/styles.css`

A single-file HTML app (no server, no build step for end users; `npm run build` creates a standalone `dist/compare.html` that works via `file://`).

**Data flow**

```
  .parquet file ──► parquet-wasm ──► JS columnar arrays
         │
         ▼
  buildSegments() ──► annotateSegments() ──► per-lap metadata
         │
         ▼
  resample() ──► 1 m bins for each channel
         │
         ▼
  renderPanel() ──► SVG polylines + axes + labels
         │
         ▼
  renderCircuitMap() ──► SVG track outline + cursor dot
```

**Module map**

| File | Responsibility |
|------|----------------|
| `main.js` | Bootstrap: load files, build segments, wire event handlers, orchestrate render cycle. |
| `appState.js` | Central `store` (loaded sessions), `state` (UI selections, zoom, colours), feature flags. |
| `pipeline.js` | Pure data transforms: `readColumns`, `buildSegments`, `resample`, `computeDeltaT`, `buildPolylinePts`, track transform maths. |
| `panels.js` | `renderPanel()` / `renderDtPanel()` — SVG string generation for each telemetry panel. |
| `circuitMap.js` | Track outline rendering, heatmap overlays, zoom arc, map legend. |
| `cursor.js` | Crosshair cursor, tooltip, drag-to-zoom interaction. |
| `ui.js` | File picker, lap pickers, session list, colour controls, zoom reset. |
| `utils.js` | Formatting, colour persistence, zoom persistence, badge helpers. |
| `constants.js` | SVG dimensions, padding, plot width. |

**Key design decisions**
- **Distance-aligned only** — x-axis is lap distance (metres), not time. All panels share the same distance grid.
- **Δt by direct subtraction** — resample `lap_time_s` onto 1 m bins for both laps, then subtract. Avoids the distance-integrator phantom error that plagued an earlier `∫ 1/speed` approach (see `rca-deltat-phantom-error.md`).
- **No caching** — every `renderAll` re-resamples from scratch. Acceptable for ~25 k-row sessions; async chunked pre-resample is the planned mitigation if friction appears.
- **Lap colours via CSS variables** — `--session` and `--ref` drive every trace, legend swatch, sector marker, and tooltip value. User-customisable with `<input type="color">`, persisted in `localStorage`.

---

## File Format

### Session file: `session_<utc>_<track>_<sim>.parquet`

One row per recorded frame. Parquet with Snappy compression. ~10× smaller than CSV; universally readable (pandas, polars, DuckDB, R, Julia, browser via parquet-wasm).

Core columns:
- `session_time_s`, `lap_number`, `lap_distance_m`, `lap_time_s`
- `speed_kph`, `throttle_norm`, `brake_norm`, `steering_norm`, `gear`, `engine_rpm`
- `pos_x_m`, `pos_y_m`, `pos_z_m` (for circuit map)
- `slip_angle_fl_deg` … `rr_deg`
- `abs_active`, `tc_active` (LMU only; nullable)

### Sidecar: `.json`

Small JSON written next to the Parquet:
```json
{
  "schema_version": "1",
  "recorder_version": "0.1.0",
  "started_utc": "2026-05-09T17:55:11Z",
  "sim": "lmu",
  "track": "Bahrain International Circuit",
  "vehicle_class": "GT3",
  "sample_rate_hz": 50,
  "row_count": 187234,
  "lap_count": 23
}
```

The sidecar is written at session start and refreshed on every shard flush so a hard kill still leaves recoverable metadata.

---

## Build

```bash
npm run build
```

Creates `product/dist/compare.html` — a standalone single file that inlines CSS and bundles JS dependencies via esbuild. Works via `file://` with no server.

---

## Data Flow at Runtime (Recorder)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  LMU / rF2  │────▶│  mmap read  │────▶│  Frame dataclass │
│  SHM tick   │     │  (copy mode)│     │  (sim-agnostic)  │
└─────────────┘     └─────────────┘     └─────────────────┘
                                                 │
              ┌──────────────────────────────────┼──────────────────────────────────┐
              │                                  │                                  │
              ▼                                  ▼                                  ▼
   ┌─────────────────────┐          ┌─────────────────────┐          ┌─────────────────────┐
   │  lap_number tick?   │          │  track/vehicle      │          │  30 s elapsed?      │
   │  → print boundary   │          │  change?            │          │  → flush_shard()    │
   └─────────────────────┘          │  → close old writer │          └─────────────────────┘
                                    │  → open new writer  │
                                    └─────────────────────┘
                                                 │
                                                 ▼
                                    ┌─────────────────────┐
                                    │  append(frame)      │
                                    │  → in-memory buffer │
                                    └─────────────────────┘
```

---

## Vendored Dependencies

| Submodule | Origin | Purpose |
|-----------|--------|---------|
| `vendor/pyLMUSharedMemory/` | TinyPedal fork | LMU shared-memory structs + mmap |
| `vendor/pyRfactor2SharedMemory/` | TinyPedal fork | rF2 shared-memory structs + mmap |

Both are the **same upstreams** TinyPedal uses, ensuring parity. We do not modify them; we only import their public API in `connect.py`.

---

## Test Scripts

Playwright-based acceptance tests in `scripts/test_*.js` exercise the comparison app end-to-end (responsive layout, walking skeleton, track outline, zoom, hover, legend, linked highlight, etc.).

Run via `npm test` (which launches a local static server and runs the full Playwright suite).
