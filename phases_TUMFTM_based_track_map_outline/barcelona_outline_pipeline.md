# Barcelona Outline Pipeline

**Status:** ✅ COMPLETE
**Completed:** 2026-05-15
**Branch:** `barcelona-outline-pipeline`
**Approach:** MEDIAN of fastest 5 complete laps from multiple sessions

**Audience:** implementing agent starting from empty context.
**Goal:** Produce a `data/track-outlines/circuit-de-barcelona.json` schema v1 outline for the LMU Barcelona-Catalunya circuit, aligned to simulator coordinates, and wire it into the frontend manifest.

---

## 1. Context

- LMU uses a **different Barcelona layout** than the TUMFTM `Catalunya.csv`. The TUMFTM data aligns poorly (verified visually by the user — "wrong version of the layout").
- TUMFTM has only one `Catalunya.csv`, no layout variants.
- ~~**bacinger/f1-circuits** provides GeoJSON centerlines~~ — **DISCARDED**: bacinger data did not match LMU's Barcelona layout at all.
- **New approach:** Generate outline directly from simulator trajectory data by tracing the recorded positions with ±5m boundaries.
- Our sessions have 26+ Barcelona parquets with `pos_x_m`/`pos_z_m` simulator trajectories.
- The existing `data/track-outlines/circuit-de-barcelona.json` was auto-aligned from TUMFTM Catalunya — it is the **wrong layout** and must be replaced.
- The frontend manifest (`web/js/trackOutlineManifest.js`) already has Barcelona wired up via `CIRCUIT_BARCELONA_STATIC_OUTLINE`; regenerating the module from the new outline is straightforward.

## 2. Data sources

### Simulator trajectory data (PRIMARY SOURCE)

- **27 Barcelona sessions** in `sessions/` directory
- **26+ complete racing laps** across all sessions (GT3 and LMP3 classes)
- Columns: `pos_x_m`, `pos_z_m` (simulator coordinates), `lap_time_s`, `lap_number`
- **Advantage:** Guaranteed to match LMU's coordinate system and layout
- **Selection:** Script picks fastest 5 complete laps (lap_time > 60s)

### Helper Scripts

1. **`scripts/explore_and_export_laps.py`** — Explore laps in a session and export selected ones:
   ```bash
   # List all laps with times
   python3 scripts/explore_and_export_laps.py sessions/session_*.parquet
   
   # Export fastest 3 complete laps
   python3 scripts/explore_and_export_laps.py sessions/session_*.parquet --fastest 3
   
   # Export specific laps
   python3 scripts/explore_and_export_laps.py sessions/session_*.parquet --export 3,5
   ```

2. **`scripts/average_trajectory_outline.py`** — Generate outline from fastest laps:
   ```bash
   # Generate outline (uses default 3 Barcelona sessions)
   python3 scripts/average_trajectory_outline.py data/track-outlines/circuit-de-barcelona.json
   ```

3. **`tools/README-GENERATE-OUTLINE.md`** — Full documentation on the pipeline

### TUMFTM Catalunya.csv — DO NOT USE for Barcelona

- Wrong layout. Already proven to not match LMU's Barcelona.
- Keep `Catalunya.csv` around in case a future LMU layout matches the TUMFTM variant.

### ~~bacinger/f1-circuits~~ — DISCARDED

- ~~Repo: https://github.com/bacinger/f1-circuits~~
- ~~File: `circuits/es-1991.geojson`~~
- **Did not work:** The GPS-derived centerline did not match LMU's Barcelona layout at all.
- **Lesson:** External GeoJSON sources may not match simulator-specific track layouts.

## 3. Subphases

### 3.1 Explore available laps ✅

1. Use `scripts/explore_and_export_laps.py` to list laps in sessions:
   ```bash
   python3 scripts/explore_and_export_laps.py sessions/session_20260514T141305Z_circuit-de-barcelona_lmu.parquet
   ```

2. Review lap times and identify complete laps (lap_time > 60s)

**Done:** Script shows all laps with times, points, and completeness status.

### 3.2 Generate outline from fastest 5 laps ✅

1. Use `scripts/average_trajectory_outline.py` to generate outline:
   ```bash
   python3 scripts/average_trajectory_outline.py data/track-outlines/circuit-de-barcelona.json
   ```

2. Script automatically:
   - Loads 3 sessions (2× GT3, 1× LMP3)
   - Filters complete laps (lap_time > 60s)
   - Selects fastest 5 laps
   - Resamples each to 500 points
   - Computes **point-wise MEDIAN** (not mean!)
   - Adds ±5m boundaries
   - Outputs schema v1 JSON

**Why MEDIAN?** Different drivers take different racing lines through corners. Mean averaging smears corners inward by ~63 sim-units. Median preserves actual track geometry.

**Result:** Outline bounds match trajectory bounds within 0.3%:
- Outline: X span 964, Y span 1157
- Trajectory: X span 967, Y span 1158

### 3.3 Regenerate the static ES module ✅

1. Run: `node scripts/generate_outline_module.js data/track-outlines/circuit-de-barcelona.json`
2. This overwrites `web/js/staticCircuitBarcelonaOutlineData.js`.
3. The manifest (`web/js/trackOutlineManifest.js`) already imports this module.

**Done:** `web/js/staticCircuitBarcelonaOutlineData.js` regenerated (72 KB).

### 3.4 Verify ✅

```bash
bash scripts/test-summary.sh
npm run build
```

**Done:** 731 assertions pass, build succeeds.

### 3.5 Visual QA ⏳ PENDING (optional)

**Recommended but optional** — the outline already matches trajectories within 0.3%.

1. Open `tools/manual_outline_align.html` in a browser.
2. Load the outline (`data/track-outlines/circuit-de-barcelona.json`) as "TUMFTM track".
3. Load a reference trajectory (e.g., `trajectory-barcelona-lap3.json`).
4. Verify landmarks:
   - Start/finish straight
   - Turn 1 (tight right after long straight)
   - Camp corner (tight left hairpin)
   - Back straight
   - Turn 10 / chicane
5. If satisfied, update `visual_qa.status` to `"accepted"` in the JSON.

### 3.6 Commit ✅

**Done:** Committed to `barcelona-outline-pipeline` branch.

## 4. Known caveats for Barcelona

- **Width is constant ±5m** — not measured from real track data. Barcelona-Catalunya is a wide F1 track; actual width varies from ~10-15m. Adjust manually if needed.
- **Median racing line** — represents the middle line across 5 fastest laps, may not match any single driver's exact line.
- **No smoothing applied** — the 500-point resampled outline should be smooth enough for visual context.
- **Layout variant:** This outline matches the LMU Barcelona layout from session data — guaranteed to be correct for this simulator.
- **Fastest laps used:** All 5 fastest laps are within ~1.5s of each other (97.24s - 98.69s), ensuring consistent racing lines.

## 5. Rollback plan

If median-based outline proves unsatisfactory:

1. Revert to single-lap trajectory approach (use `scripts/trajectory_to_outline.py` on one clean lap).
2. Try OSM Overpass extraction for real-world geometry (but may not match LMU layout).
3. Remove the Barcelona outline and let the app render trajectory-only (graceful fallback).

**Note:** The median-of-fastest-laps approach is the most robust — it uses the simulator's own coordinate system and filters out incomplete laps while preserving corner geometry.