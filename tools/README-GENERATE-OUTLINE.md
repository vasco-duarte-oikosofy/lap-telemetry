# Generate Track Outline from Trajectory Data

This guide explains how to generate a track outline JSON file from simulator session data.

## Overview

The `scripts/average_trajectory_outline.py` script generates a schema v1 track outline by:

1. Loading multiple session parquet files
2. Extracting **complete racing laps** (filters out-laps/in-laps)
3. Selecting the **fastest 5 laps** across all sessions
4. Computing a **point-wise MEDIAN** trajectory (robust to different racing lines)
5. Adding ±5m boundaries
6. Outputting a schema v1 outline JSON

## Why MEDIAN?

Different drivers take different racing lines through corners (early apex vs late apex). Using **mean** averaging would smear corners inward. **Median** picks the middle racing line, preserving actual track geometry.

**Result:** Outline bounds match trajectory bounds within 0.3%.

---

## Quick Start

### Generate outline with default sessions

```bash
# Default: 3 Barcelona sessions (2× GT3, 1× LMP3)
python3 scripts/average_trajectory_outline.py data/track-outlines/circuit-de-barcelona.json
```

### Register Outline (Single Command)

```bash
python3 scripts/register_outline.py data/track-outlines/bahrain_outline.json
```

This command:
1. Validates the outline JSON structure
2. Generates the ES module (`web/js/static<Track>OutlineData.js`)
3. Creates a backup of the manifest (`web/js/trackOutlineManifest_backup.js`)
4. Adds import statement to `web/js/trackOutlineManifest.js`
5. Registers all track name variants in the OUTLINES map
6. Rebuilds `dist/compare.html`

**Result:** Outline is immediately visible in compare.html — no manual steps needed.

The script is **idempotent**: running it twice makes no changes on the second run.

### Verify

```bash
bash scripts/test-summary.sh
npm run build
```

---

## Custom Sessions

To use different sessions, pass them with `--sessions`:

```bash
python3 scripts/average_trajectory_outline.py data/track-outlines/circuit-de-barcelona.json \
  --sessions \
    sessions/session_20260514T141305Z_circuit-de-barcelona_lmu.parquet \
    sessions/session_20260510T124244Z_circuit-de-barcelona_lmu.parquet
```

---

## How It Works

### 1. Load Sessions

The script loads parquet files from `sessions/` directory. Each session contains telemetry data with:
- `pos_x_m`, `pos_z_m` — simulator coordinates
- `lap_number` — lap identifier
- `lap_time_s` — lap time (populated for complete laps)
- `lap_distance_m` — distance along lap

### 2. Filter Complete Laps

A lap is considered **complete** if:
- `lap_number >= 1` (skips lap 0, often an out-lap)
- `lap_time_s > 60.0` (filters in-laps, out-laps, aborted laps)
- Has at least 100 data points

Example output:
```
Loading 3 sessions...
  session_20260510T124244Z_circuit-de-barcelona_lmu.parquet: 5 complete laps
    Lap 1: 111.71s
    Lap 2: 99.89s
    Lap 3: 99.18s
    Lap 4: 98.14s
    Lap 5: 97.74s
  session_20260511T151203Z_circuit-de-barcelona_lmu.parquet: 4 complete laps
    Lap 1: 115.17s
    Lap 2: 104.77s
    Lap 3: 104.69s
    Lap 4: 103.96s
  session_20260514T141305Z_circuit-de-barcelona_lmu.parquet: 5 complete laps
    Lap 1: 100.27s
    Lap 2: 98.69s
    Lap 3: 97.99s
    Lap 4: 104.59s
    Lap 5: 97.24s

Total: 14 complete laps
```

### 3. Select Fastest 5 Laps

The script sorts all complete laps by lap time and picks the fastest 5:

```
Selecting fastest 5 laps:
  1. session_20260514T141305Z_circuit-de-barcelona_lmu.parquet lap 5: 97.24s
  2. session_20260510T124244Z_circuit-de-barcelona_lmu.parquet lap 5: 97.74s
  3. session_20260514T141305Z_circuit-de-barcelona_lmu.parquet lap 3: 97.99s
  4. session_20260510T124244Z_circuit-de-barcelona_lmu.parquet lap 4: 98.14s
  5. session_20260514T141305Z_circuit-de-barcelona_lmu.parquet lap 2: 98.69s
```

### 4. Resample to 500 Points

Each lap is resampled to exactly 500 evenly-spaced points along the lap distance. This ensures all laps have the same point count for averaging.

### 5. Compute MEDIAN Centerline

For each of the 500 point positions, the script computes the **median** X and Y coordinates across all 5 laps:

```python
for i in range(500):
    xs = [lap[i]['x'] for lap in resampled_laps]
    ys = [lap[i]['y'] for lap in resampled_laps]
    median_x = float(np.median(xs))
    median_y = float(np.median(ys))
    centerline.append({'x': median_x, 'y': median_y})
```

**Why median?** Different drivers apex corners at different points. Mean averaging would smear corners inward. Median preserves the actual track geometry.

### 6. Compute Boundaries

Left and right boundaries are computed at ±5m perpendicular to the track direction at each point.

### 7. Output Schema v1 JSON

The output JSON includes:
- `centerline` — 500 points
- `left_boundary` — 500 points
- `right_boundary` — 500 points
- `alignment` — metadata about sessions and laps used
- `visual_qa` — status field for QA tracking

---

## Validate the Output

### 1. Visual Validation

Open the validation tool:

```bash
# Serve locally
python3 -m http.server 8000

# Open in browser
open http://localhost:8000/tools/validate_barcelona_outline.html
```

Or use the manual alignment tool:

```bash
open tools/manual_outline_align.html
```

Load:
- **Slot 1 (Reference trajectory):** `data/track-outlines/alignment-artifacts/circuit-de-barcelona/trajectory-barcelona-lap3.json`
- **Slot 2 (Outline):** `data/track-outlines/circuit-de-barcelona.json`

The outline and trajectory should overlay almost perfectly at scale 1.0.

### 2. Check Bounds

```bash
python3 << 'EOF'
import json

with open('data/track-outlines/circuit-de-barcelona.json') as f:
    outline = json.load(f)

xs = [p['x'] for p in outline['centerline']]
ys = [p['y'] for p in outline['centerline']]
print(f"X: {min(xs):.0f}..{max(xs):.0f} (span: {max(xs)-min(xs):.0f})")
print(f"Y: {min(ys):.0f}..{max(ys):.0f} (span: {max(ys)-min(ys):.0f})")
EOF
```

Expected output (Barcelona):
```
X: -651..314 (span: 964)
Y: -491..666 (span: 1157)
```

### 3. Run Tests

```bash
bash scripts/test-summary.sh
npm run build
```

---

## Output Format

The output is a **schema v1** track outline JSON:

```json
{
  "schema_version": 1,
  "source": "Median trajectory from 5 fastest complete laps",
  "track_name": "Circuit de Barcelona-Catalunya",
  "sim_track_name": "Circuit de Barcelona",
  "layout_name": "default",
  "coordinate_system": "sim_xy",
  "units": "sim_units",
  "track_name_mapping": { ... },
  "alignment": {
    "method": "median_trajectory_average",
    "width_per_side": 5.0,
    "lap_count": 5,
    "session_count": 3,
    "sessions": [...],
    "fastest_laps": [
      {"session": "...", "lap_number": 5, "lap_time_s": 97.24},
      ...
    ],
    "notes": "Uses point-wise MEDIAN instead of mean..."
  },
  "visual_qa": {
    "status": "pending",
    "notes": "..."
  },
  "caveats": [...],
  "centerline": [{"x": ..., "y": ...}, ...],
  "left_boundary": [{"x": ..., "y": ...}, ...],
  "right_boundary": [{"x": ..., "y": ...}, ...]
}
```

---

## Troubleshooting

### "No complete laps found"

Check that your parquet files have:
- `lap_number` column
- `lap_time_s` column (populated for complete laps)
- `pos_x_m` and `pos_z_m` columns

### Outline doesn't match trajectory

1. Check that you're using sessions from the **same track layout**
2. Verify lap times — all selected laps should be similar (within ~5s)
3. Check bounds — outline span should match trajectory span within 5%

### Outline is too small

This was the original bug — using MEAN instead of MEDIAN. Make sure you're using the latest version of the script.

---

## Example: New Track

To generate an outline for a new track (e.g., Spa):

```bash
# 1. Find Spa sessions
ls sessions/*spa*.parquet

# 2. Generate outline
python3 scripts/average_trajectory_outline.py data/track-outlines/spa-francorchamps.json \
  --sessions \
    sessions/session_20260510T173248Z_circuit-de-spa-francorchamps_lmu.parquet \
    sessions/session_20260511T183100Z_circuit-de-spa-francorchamps_lmu.parquet

# 3. Register outline (generates ES module + updates manifest + rebuilds)
python3 scripts/register_outline.py data/track-outlines/spa-francorchamps.json
```

---

## See Also

- `tools/manual_outline_align.html` — Manual alignment and QA tool
- `tools/validate_barcelona_outline.html` — Barcelona-specific validation
- `scripts/generate_outline_module.js` — Converts outline JSON to ES module
- `web/js/trackOutlineManifest.js` — Manifest mapping track names to outlines

---

## Best Practice: Use Single Fastest Lap (Not Averaged)

**TL;DR:** For smooth outlines, use the **single fastest lap** instead of averaging multiple laps.

### Why Single Lap > Averaged?

When you average multiple laps (even with MEDIAN), you get **jitter in corners** because different drivers take different racing lines:

- Driver A apexes Turn 3 at point 150
- Driver B apexes Turn 3 at point 155
- **Point-by-point averaging** creates intermediate positions that match neither driver

This creates visible zigzag/jitter in the outline, especially in tight corners.

### Recommended Workflow:

```bash
# 1. Explore laps and find fastest
python3 scripts/explore_and_export_laps.py sessions/session_*.parquet --fastest 1

# 2. Export fastest lap
python3 scripts/explore_and_export_laps.py sessions/session_*.parquet --export 8

# 3. Generate outline from single lap
python3 scripts/average_trajectory_outline.py data/track-outlines/track_outline.json \
  --laps data/track-outlines/alignment-artifacts/exported-laps/lap8.json
```

### Result:

- ✅ **Smooth centerline** — no averaging artifacts
- ✅ **Perfect alignment** — matches trajectory exactly
- ✅ **Real racing line** — from fastest (cleanest) lap

### When to Average:

Averaging multiple laps is only useful when:
- You want to find the "typical" racing line across multiple drivers
- All drivers take nearly identical lines (e.g., simple ovals)
- You're doing analysis, not generating visual outlines

For **track outline generation**, always prefer **single fastest lap**.

---

## Manual Alignment with `tools/manual_outline_align.html`

The `manual_outline_align.html` tool lets you visually verify and refine track outlines.

### Opening the Tool

```bash
# Serve files locally
python3 -m http.server 8000

# Open in browser
open http://localhost:8000/tools/manual_outline_align.html
```

### Loading Files

1. **Slot 1: Simulator reference trajectory**
   - Load an exported lap JSON (e.g., `data/track-outlines/alignment-artifacts/exported-laps/lap8.json`)
   - This shows the actual driven trajectory

2. **Slot 2: TUMFTM track JSON (outline)**
   - Load your generated outline (e.g., `data/track-outlines/bahrain_outline.json`)
   - This shows the outline boundaries

3. **Slot 3 (Optional): Extra trajectories**
   - Load additional laps to compare multiple driving lines

### Controls

| Control | Action |
|---------|--------|
| **Mouse drag** | Pan the view |
| **Mouse wheel** | Zoom in/out |
| **Arrow keys** | Translate outline (fine adjustment) |
| **Shift + Arrows** | Translate outline (coarse) |
| **Q / E** | Rotate outline |
| **+ / -** | Scale outline |
| **F** | Cycle flip options |
| **R** | Reverse point order |

### Visual QA Checklist

Verify these landmarks align between trajectory and outline:

- [ ] **Start/finish straight** — should be straight and properly oriented
- [ ] **Turn 1** — tight right-hander after long straight
- [ ] **Key corner apexes** — outline should follow trajectory through corners
- [ ] **Back straight** — length and orientation match
- [ ] **Final corner** — flows naturally into start/finish

### Exporting Refined Outline

If the outline needs adjustment:

1. Use controls to align outline with trajectory
2. Click **"Export aligned outline JSON"**
3. Save the exported JSON
4. Replace your outline file with the exported version
5. Register outline: `python3 scripts/register_outline.py <outline.json>` (also regenerates ES module)

### Expected Result

For a **single-lap outline**, the trajectory and outline should overlay **perfectly at scale 1.0** with no adjustment needed. If they don't match, check:

- Both files are from the **same track layout**
- Both use the **same coordinate system** (simulator coordinates)
- The lap wasn't an out-lap/in-lap (check lap_time > 60s)

---

## Troubleshooting: Outline Not Showing in `dist/compare.html`

If your outline doesn't appear in the comparison viewer:

### 1. Check the Track Name Mapping

The outline's `track_name_mapping` must match the session's track name:

```json
{
  "track_name_mapping": {
    "canonical_sim_track_name": "bahrain-international-circuit",
    "accepted_sim_track_names": ["bahrain-international-circuit", "Bahrain International Circuit"]
  }
}
```

### 2. Register Outline

```bash
python3 scripts/register_outline.py data/track-outlines/bahrain_outline.json
```

This generates the ES module, registers the outline in the manifest, and rebuilds `dist/compare.html`.

### 3. Verify in Browser Console

Open `dist/compare.html` and check console for:
- `Loaded outline for track: Bahrain International Circuit` (success)
- `No outline found for track: ...` (name mismatch)

