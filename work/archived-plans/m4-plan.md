# M4 — Comparison app, single speed-vs-distance plot

**Goal:** Ship `web/compare.html` — a self-contained HTML file the user opens
in any modern browser (no server, no build step, internet required for CDN
deps). Two file inputs: session parquet + reference-lap parquet. A lap picker
over chronological segments. Speed-vs-distance overlay of the chosen lap
against the reference. Also fold in the O1/O2 sector-lookup timing fix from
DESIGN §10.

---

## Scope

### A. Fix O1/O2 — sector-lookup timing (summary.py)

**Problem.** `summary.py` reads `mLastSector*` from the *literal first frame*
of the next segment. On some lap boundaries the SHM is mid-update at that
tick, so `s1 == 0` (O1: lap shows `-`) or carries stale values from the lap
before (O2: consecutive laps display identical S1/S2).

**Fix.** After locating `next_start` (first frame index of the following
segment), walk forward up to 25 frames (≈0.5 s at 50 Hz) inside that segment
to find the first frame where `s1 > 0 and cum_s2 > s1`. If no frame in that
window satisfies the condition, show `-` as before. Cap the walk at
`min(next_start + 25, next_segment_end)` so we never cross into a third
segment.

**Acceptance.** `lap-telemetry summary sessions/session_20260510T093245Z_*`
must show non-dash sector splits for lap 3 (currently `-` due to O1). Each
middle lap: `s1 + s2 + s3 ≈ duration` within 0.05 s.

### B. Reference lap fixture

**What.** `scripts/extract_reference_lap.py` reads a session parquet, builds
chronological segments (same logic as M3), extracts the Nth segment by
1-indexed chronological position, and writes a new parquet containing only
those rows.

**Default invocation:**
```
python scripts/extract_reference_lap.py \
  sessions/session_20260510T093245Z_circuit-de-barcelona_lmu.parquet \
  --segment 5 \
  --out sessions/reference_lap_circuit-de-barcelona_lap5.parquet
```
Segment 5 = chronological position 5 = lap_number 5 at 1:37.834 (fastest clean
lap in the 6-lap session).

**Why a separate file.** The comparison app's reference-lap input is a plain
parquet; the app treats all rows in it as a single lap. A simple slice-and-write
is cleaner than embedding segment-selection logic in the HTML and less fragile
than asking the user to slice files manually.

### C. HTML comparison app — `web/compare.html`

A single file with all JS/CSS inline. Dependencies loaded from CDN (internet
required):
- **hyparquet** — pure-JS parquet decoder (no WASM)
- **hyparquet-compressors** — Snappy decoder for compressed Parquet files

Both loaded via `<script type="module">` from JSDelivr. All plot logic written
in pure SVG (no D3 or chart library needed for a single line overlay).

#### Parquet loading

`File → ArrayBuffer slice interface → parquetRead()`. Reads only the three
columns needed for M4: `lap_number`, `lap_distance_m`, `speed_kph`. Handles
the reference file the same way but skips the segment-builder (whole file = one
lap).

#### Lap picker

Builds chronological segments from `lap_number` (same algorithm as M3
`_build_segments`). Displays as:

```
Lap 1 — lap# 1  (out lap)
Lap 2 — lap# 2  1:38.5
Lap 3 — lap# 3  1:38.0
Lap 4 — lap# 4  1:37.8
Lap 5 — lap# 5  1:37.8  ★ best
Lap 6 — lap# 6  (in lap)
```

1-indexed chronological position with the raw `lap_number` alongside.
Post-restart duplicate `lap_number` values get distinct picker entries (as
in the restart-session fixture where lap_numbers …7, 0, 1 appear).

First and last segment labelled as "out lap" / "in lap" respectively (they
can still be selected and plotted, but are marked).

Lap duration computed from `max(lap_time_s)` within the segment — same
approach as `summary.py`.

#### Resampler

1. Filter session rows to the chosen segment.
2. Sort `(lap_distance_m, speed_kph)` pairs by distance.
3. Bin to 1 m intervals: `bins = [0, 1, 2, ..., ceil(max_distance)]`.
4. Linear interpolation for each bin position.
5. Same algorithm applied to the reference lap (all rows).

Both resampled arrays share the same x-axis length (max of their bin counts).

Exposed as `window.__resamplerDebug(segIdx)` for the Playwright cross-check
test.

#### SVG plot

Dimensions: 900 × 400 px, auto-scaled to speed and distance ranges of the
two laps. Two `<polyline>` elements (session = `#4fc3f7` blue,
reference = `#ff9800` orange). Axes drawn as `<line>` elements with tick
marks and numeric labels. Legend in top-right corner.

#### Layout

Single column:
- Header ("Lap Compare")
- Two file inputs with status badges (loading / N rows loaded / error)
- Lap picker `<select>` + "Compare" button (enabled only when both files loaded)
- SVG plot area
- Error message area

Dark theme (monospace, `#1a1a2e` background) for consistency with TinyPedal.

### D. AFK testing suite

#### 1. `scripts/extract_reference_lap.py`

Run first to produce the reference-lap fixture. Not shipped as a
`lap-telemetry` CLI subcommand — it's a one-shot helper.

#### 2. `scripts/check_resampler.py`

Python equivalent of the browser resampler:
```python
import pyarrow.parquet as pq, numpy as np, json, sys
t = pq.read_table(sys.argv[1], columns=["lap_distance_m", "speed_kph"])
xs, ys = np.array(t["lap_distance_m"]), np.array(t["speed_kph"])
order = np.argsort(xs); xs, ys = xs[order], ys[order]
bins = np.arange(0, int(np.ceil(xs.max())) + 1)
resampled = np.interp(bins, xs, ys)
print(json.dumps(resampled.tolist()))
```

Used by the Playwright test to cross-check browser resampler output:
`max|python_speed − browser_speed| < 0.1 km/h`.

#### 3. `scripts/test_m4.js`

Playwright test (Node.js) that:
1. Spins up a tiny `http.createServer` at localhost:8765 serving
   `web/compare.html` (avoids file:// CDN CORS complications).
2. Launches Chromium headless.
3. Opens `http://localhost:8765`.
4. **State 1 — initial.** Screenshot. Assert picker is disabled.
5. **Load session.** `page.setInputFiles('#session-input', <path>)`.
   Wait for `#session-status` to contain "rows". Screenshot.
6. **Assert picker options.** 6 for the clean session; 7 for the restart session.
7. **Load reference.** `page.setInputFiles('#ref-input', <path>)`.
   Wait for `#ref-status` to contain "rows". Screenshot.
8. **Pick a lap.** Select segment index 3 (lap 4 in the clean session).
   Click "Compare". Wait for `<polyline>` elements. Screenshot.
9. **DOM assertion.** Count `<polyline>` elements == 2.
10. **Resampler cross-check.** Call `window.__resamplerDebug(3)` via
    `page.evaluate()`; write result to `m4-test-report/browser_resampled.json`.
    Run `check_resampler.py` on the reference lap; compare; write diff stats.
11. **Console log.** Capture all browser console messages; write to
    `m4-test-report/console.log`. Fail the test if any `error` or `warn` entry.
12. **Second fixture.** Repeat steps 5–9 with the restart-session file;
    assert 7 picker options.
13. Write `m4-test-report/REPORT.md` summarising all assertions.

#### Playwright setup

```
npm install --save-dev playwright
npx playwright install chromium
```

Run: `node scripts/test_m4.js`

---

## Steps

1. **Fix O1/O2** — edit `summary.py` `_run_file`; walk up to 25 frames for
   sector lookup. Run smoke test; confirm lap 3 sectors appear.
2. **Write `scripts/extract_reference_lap.py`**; run it; confirm output file.
3. **Write `web/compare.html`** in order: HTML skeleton → CSS dark theme →
   parquet load → segment builder → lap picker → resampler (+debug hook) →
   SVG plot renderer → event wiring.
4. **Install Playwright** in the project dir.
5. **Write `scripts/check_resampler.py`**.
6. **Write `scripts/test_m4.js`**; run against both fixtures; diagnose and fix
   any failures.
7. **Final smoke test:** `lap-telemetry summary sessions/session_20260510T093245Z_*.parquet`
   (must still pass after summary.py changes).
8. **Update `.gitignore`** to exclude `m4-test-report/` and `node_modules/`.
9. **Commit** everything except the test-report directory.

---

## Acceptance tests

All must hold simultaneously:

| ID  | Test |
|-----|------|
| T1  | `lap-telemetry summary …093245Z_*.parquet` shows non-dash S1/S2/S3 for **all** middle laps including lap 3; `s1+s2+s3 ≈ duration` ±0.05 s. |
| T2  | `sessions/reference_lap_circuit-de-barcelona_lap5.parquet` exists; row count ≈ 4894 (±5 for boundary frames). |
| T3  | Playwright / clean session: picker has **6** options; picking lap 4 renders two `<polyline>` in the SVG; zero console errors. |
| T4  | Playwright / restart session: picker has **7** options in chronological order (3,4,5,6,7,0,1); two polylines after picking any middle lap. |
| T5  | Resampler diff: `max|browser − python| < 0.1 km/h` for the reference lap. |
| T6  | `lap-telemetry record --once` exits 0 (recorder smoke test, if LMU is running). |

---

## M5 notes (document for later review)

These are explicitly deferred from M4 and should shape M5 scope:

- **Unified loading.** Replace the two-file-input flow with a single session
  loader that exposes all laps from one or more loaded sessions. User picks
  "session lap" and "reference lap" from the same picker (filtered by session).
  No need to pre-slice a separate reference-lap parquet.
- **Full plot stack.** Throttle/brake overlay, RPM/gear, steering angle,
  per-axle slip, Δt-vs-distance. All panels linked to a shared lap-distance
  x-axis with a synced vertical hairline cursor.
- **Sector markers.** Vertical lines at the S1 and S2 distances (derived from
  `last_sector_1_s`, `last_sector_2_s`, and average speed at the time).
- **Lap filter.** Checkbox to hide out/in laps; invalid laps visually marked
  in the picker (greyed out or ⚠ badge).
- **Persistent state.** localStorage for last-used file paths (browser
  `FileSystemFileHandle` API, Chrome only but acceptable for v0.1 users).
- **M4 limitation to document in M5 notes.** The two-upload flow requires the
  user to pre-extract a reference lap with `scripts/extract_reference_lap.py`.
  M5 eliminates this friction by allowing any lap from any loaded session to
  be the reference.
