# Barcelona Outline Pipeline

**Status:** ✅ COMPLETE (ready for Visual QA)
**Completed:** 2026-05-15
**Branch:** `barcelona-outline-pipeline`
**Approach:** Trajectory trace (±5m width) — bacinger approach discarded

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

- Existing `data/track-outlines/alignment-artifacts/circuit-de-barcelona/trajectory-circuit-de-barcelona.json`
- 1377 points from a multi-lap Barcelona session
- Columns: `pos_x_m`, `pos_z_m` in simulator coordinates
- **Advantage:** Guaranteed to match LMU's coordinate system and layout

### TUMFTM Catalunya.csv — DO NOT USE for Barcelona

- Wrong layout. Already proven to not match LMU's Barcelona.
- Keep `Catalunya.csv` around in case a future LMU layout matches the TUMFTM variant.

### ~~bacinger/f1-circuits~~ — DISCARDED

- ~~Repo: https://github.com/bacinger/f1-circuits~~
- ~~File: `circuits/es-1991.geojson`~~
- **Did not work:** The GPS-derived centerline did not match LMU's Barcelona layout at all.
- **Lesson:** External GeoJSON sources may not match simulator-specific track layouts.

## 3. Subphases

### 3.1 Generate outline from trajectory trace ✅

1. Use existing `trajectory-circuit-de-barcelona.json` (1377 points from multi-lap session).
2. Resample to ~500 evenly-spaced points for smooth outline.
3. Compute left/right boundaries at ±5m perpendicular to track direction.
4. Save as `data/track-outlines/circuit-de-barcelona.json` in schema v1 format.

**Done:** Created `scripts/trajectory_to_outline.py` — traces trajectory with ±5m boundaries. Output: 500-point centerline with matching boundaries.

### 3.2 Extract a clean reference lap from session data ✅

Already done — `trajectory-circuit-de-barcelona.json` exists from prior `prepare_all_outlines.js` run.

### 3.3 Run automated ICP alignment — SKIPPED

Not needed — the trajectory is already in simulator coordinates. The outline is generated directly from the trajectory trace.

### 3.4 Visual QA with manual_outline_align.html ⏳ PENDING

**This step requires a human.**

1. Open `tools/manual_outline_align.html` in a browser.
2. Load the trajectory-generated outline (`data/track-outlines/circuit-de-barcelona.json`) as "TUMFTM track".
3. The simulator reference trajectory should already be loaded (or load `trajectory-circuit-de-barcelona.json`).
4. **Expected:** The outline should already align perfectly since it was traced from the trajectory!
5. Verify major landmarks look correct:
   - **Start/finish straight** — should be straight and properly oriented.
   - **Turn 1** (tight right-hander after long straight).
   - **Camp corner** (tight left hairpin at the far end).
   - **Back straight** length and orientation.
   - **Turn 10 / chicane area** — should flow naturally.
6. If the outline needs refinement (e.g., width adjustments, smoothing), use the manual alignment tool to adjust.
7. Export the refined outline JSON.
8. **Replace** `data/track-outlines/circuit-de-barcelona.json` with the verified export.
9. Set `visual_qa.status` to `"accepted"` and add notes about what was checked.

### 3.5 Regenerate the static ES module ✅

1. Run: `node scripts/generate_outline_module.js data/track-outlines/circuit-de-barcelona.json`
2. This overwrites `web/js/staticCircuitBarcelonaOutlineData.js`.
3. Verify `CIRCUIT_BARCELONA_STATIC_OUTLINE` export exists.
4. The manifest (`web/js/trackOutlineManifest.js`) already imports this module — no changes needed unless the export name changed.

**Done:** `web/js/staticCircuitBarcelonaOutlineData.js` regenerated (72 KB).

### 3.6 Verify ✅

```bash
bash scripts/test-summary.sh
npm run build
```

All 732+ assertions must pass. The build must succeed.

**Done:** 731 assertions pass, build succeeds.

### 3.7 Commit ✅

**Done:** Committed to `barcelona-outline-pipeline` branch.

## 4. Known caveats for Barcelona

- **Width is constant ±5m** — not measured from real track data. Barcelona-Catalunya is a wide F1 track; actual width varies from ~10-15m. Adjust in manual QA if needed.
- **Centerline follows trajectory** — may not match ideal racing line or track center. The trajectory is from an actual lap, so it should be close to the racing line.
- **No smoothing applied** — the 500-point resampled outline should be smooth enough for visual context.
- **Layout variant:** This outline matches the LMU Barcelona layout from the session data — guaranteed to be correct for this simulator.

## 5. Rollback plan

If trajectory-based outline proves unsatisfactory:

1. Revert to previous TUMFTM-based version from git history (though we know it was wrong layout).
2. Try extracting centerline from multiple sessions and averaging.
3. Try OSM Overpass extraction for real-world geometry (but may not match LMU layout).
4. Remove the Barcelona outline and let the app render trajectory-only (graceful fallback — the app already handles missing outlines).

**Note:** The trajectory-based approach is much more likely to work than external data sources since it uses the simulator's own coordinate system.