# Barcelona Outline Pipeline

**Audience:** implementing agent starting from empty context.
**Goal:** Produce a `data/track-outlines/circuit-de-barcelona.json` schema v1 outline for the LMU Barcelona-Catalunya circuit, aligned to simulator coordinates, and wire it into the frontend manifest.

---

## 1. Context

- LMU uses a **different Barcelona layout** than the TUMFTM `Catalunya.csv`. The TUMFTM data aligns poorly (verified visually by the user — "wrong version of the layout").
- TUMFTM has only one `Catalunya.csv`, no layout variants.
- **bacinger/f1-circuits** provides GeoJSON centerlines (lon/lat, no widths, no boundaries) for Barcelona: `circuits/es-1991.geojson`.
- Our sessions have 26+ Barcelona parquets with `pos_x_m`/`pos_z_m` simulator trajectories.
- The existing `data/track-outlines/circuit-de-barcelona.json` was auto-aligned from TUMFTM Catalunya — it is the **wrong layout** and must be replaced.
- The frontend manifest (`web/js/trackOutlineManifest.js`) already has Barcelona wired up via `CIRCUIT_BARCELONA_STATIC_OUTLINE`; regenerating the module from the new outline is straightforward.

## 2. Data sources

### bacinger/f1-circuits — centerline (no widths)

- **Repo:** https://github.com/bacinger/f1-circuits (312★, MIT license)
- **File:** `circuits/es-1991.geojson`
- **Format:** GeoJSON `LineString`, lon/lat (WGS84), 150 points
- **No width data.** Widths must be estimated.
- **Interactive map:** https://svemir.co/f1/

### Our session trajectories

- 26+ parquet files matching `*circuit-de-barcelona*.parquet`
- Columns: `lap_number`, `pos_x_m`, `pos_z_m`, `lap_distance_m`, etc.
- Pick a clean complete lap (not out-lap) from a multi-lap session.

### TUMFTM Catalunya.csv — DO NOT USE for Barcelona

- Wrong layout. Already proven to not match LMU's Barcelona.
- Keep `Catalunya.csv` around in case a future LMU layout matches the TUMFTM variant.

## 3. Subphases

### 3.1 Download bacinger centerline and convert to local metric coordinates

1. Download `es-1991.geojson` from bacinger/f1-circuits.
2. Parse the GeoJSON `LineString` coordinates (lon, lat).
3. Convert WGS84 lon/lat → local metric coordinates using a UTM projection (zone 31T for Barcelona, EPSG:32631).
4. Save as JSON in `data/track-outlines/alignment-artifacts/circuit-de-barcelona/bacinger-barcelona.json` using the same format our alignment tool consumes: `{ track_name, points: [{ x, y, w_right, w_left }] }`.
5. Assign estimated widths. Strategy: use a constant width (e.g. `w_right = 6, w_left = 6` for ~12m total). Barcelona-Catalunya is a wide F1 track; 6m per side is reasonable. If initial alignment looks too narrow or wide, adjust by ±1m.
6. Optionally measure actual widths from Google Maps satellite imagery at 3-5 reference points (start/finish, Turn 1, Camp hairpin, back straight, last corner) and interpolate. Only do this if constant width looks clearly wrong after visual QA.

### 3.2 Extract a clean reference lap from session data

1. Use `scripts/prepare_manual_outline_inputs.js` to export a trajectory from a Barcelona session parquet. Pick a session with 5+ laps. Pick a middle lap (not the first or last in the session, to avoid out-lap anomalies).
2. Save as `data/track-outlines/alignment-artifacts/circuit-de-barcelona/trajectory-circuit-de-barcelona.json`.
3. If we already have one from a prior `prepare_all_outlines.js` run, we can reuse it — but note the previous one used TUMFTM Catalunya; the **trajectory itself is fine**, only the TUMFTM track data was wrong.

### 3.3 Run automated ICP alignment

1. Use `scripts/auto_align_outline.js` with `--try-all-flips` against the bacinger centerline (from 3.1) and the sim trajectory (from 3.2).
2. Verify the ICP converges to a low error (< 10 sim-units mean distance).
3. The ICP pipeline resamples both curves internally so stride doesn't matter.
4. Save intermediate alignment to `data/track-outlines/circuit-de-barcelona.json`.

### 3.4 Visual QA with manual_outline_align.html

**This step requires a human.**

1. Open `tools/manual_outline_align.html` in a browser.
2. Load the bacinger JSON (from 3.1) as "TUMFTM track".
3. Load the trajectory JSON (from 3.2) as "Simulator reference trajectory".
4. Verify the auto-aligned centerline follows the sim trajectory. Major landmarks to check:
   - **Start/finish straight** alignment.
   - **Turn 1** (tight right-hander after long straight).
   - **Camp corner** (tight left hairpin at the far end).
   - **Back straight** length and orientation.
   - **Turn 10 / chicane area** — should line up without a visible kink or offset.
5. If alignment is off, manually adjust scale/rotation/translation/flip in the tool.
6. Export the aligned outline JSON.
7. **Replace** `data/track-outlines/circuit-de-barcelona.json` with the visually-verified export.
8. Set `visual_qa.status` to `"accepted"` and add notes about what was checked.

### 3.5 Regenerate the static ES module

1. Run: `node scripts/generate_outline_module.js data/track-outlines/circuit-de-barcelona.json`
2. This overwrites `web/js/staticCircuitBarcelonaOutlineData.js`.
3. Verify `CIRCUIT_BARCELONA_STATIC_OUTLINE` export exists.
4. The manifest (`web/js/trackOutlineManifest.js`) already imports this module — no changes needed unless the export name changed.

### 3.6 Verify

```bash
bash scripts/test-summary.sh
npm run build
```

All 732+ assertions must pass. The build must succeed.

### 3.7 Commit

Commit with message like:
```
feat: barcelona outline from bacinger/f1-circuits centerline + width estimation + ICP alignment

Replaces the incorrect TUMFTM Catalunya-based alignment with bacinger/f1-circuits
es-1991.geojson centerline (correct LMU Barcelona layout). Widths estimated
at ~12m constant. Visual QA pending.
```

## 4. Known caveats for Barcelona

- **Widths are estimated**, not measured from satellite. bacinger provides no width data.
  The TUMFTM Catalunya.csv width data CANNOT be transferred because it belongs to a different layout.
  If visual QA reveals width issues, measure from satellite at key points.
- **bacinger centerline is GPS-derived**, not smoothed like TUMFTM. It may have minor noise.
  The ICP alignment is robust to this, but the outline may show small jitter in tight corners.
  Smoothing can be applied offline if needed.
- **Layout variant**: bacinger `es-1991` presumably represents the post-1991 GP layout.
  LMU's Barcelona layout should match this (modern F1 layout). If LMU uses a vintage or
  MotoGP variant, the centerline will not match and we need a different source.

## 5. Rollback plan

If bacinger centerline proves wrong for LMU's Barcelona layout:
1. Revert `data/track-outlines/circuit-de-barcelona.json` to the previous TUMFTM-based version.
2. Try OSM Overpass extraction for the exact layout LMU uses.
3. If no data source matches, remove the Barcelona outline and let the app render trajectory-only (graceful fallback).