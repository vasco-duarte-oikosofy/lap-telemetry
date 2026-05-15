# Spec: Multi-Track TUMFTM Outline Alignment Pipeline

**Audience:** implementing agent starting from empty context.
**Goal:** For every LMU simulator track that has session data in `sessions/`, generate a `data/track-outlines/<slug>.json` aligned outline file and wire it into the frontend so the track map renders boundaries behind the trajectory.

---

## 1. Current state

| Track (sim slug) | Session data? | TUMFTM CSV? | Outline file? | Frontend? |
|---|---|---|---|---|
| `circuit-de-spa-francorchamps` | ✅ | `Spa.csv` | ✅ `spa-francorchamps.json` | ✅ via manifest |
| `circuit-de-spa-francorchamps-endurance` | ✅ | Same Spa outline | ✅ covered by spa outline | ✅ via manifest alias |
| `circuit-de-barcelona` | ✅ | `Catalunya.csv` | ✅ `circuit-de-barcelona.json` (auto-aligned, pending visual QA) | ✅ via manifest |
| `autodromo-enzo-e-dino-ferrari` (Imola) | ✅ | ❌ not in TUMFTM | ❌ | ❌ |
| `fuji-speedway` | ✅ | ❌ not in TUMFTM | ❌ | ❌ |

Tracks without TUMFTM data cannot be aligned with this pipeline. A future spec should address alternative data sources or hand-drawn outlines.

---

## 2. TUMFTM data source

The TUMFTM racetrack database lives at:
- **Repo:** https://github.com/TUMFTM/racetrack-database
- **License:** LGPL-3.0
- **Track CSVs:** `https://raw.githubusercontent.com/TUMFTM/racetrack-database/master/tracks/<Name>.csv`
- **Available tracks:** Austin, BrandsHatch, Budapest, **Catalunya**, Hockenheim, IMS, Melbourne, MexicoCity, Montreal, Monza, MoscowRaceway, Norisring, Nuerburgring, Oschersleben, Sakhir, SaoPaulo, Sepang, Shanghai, Silverstone, Sochi, **Spa**, Spielberg, Suzuka, YasMarina, Zandvoort

### CSV format
```
# x_m,y_m,w_tr_right_m,w_tr_left_m
-0.473164,0.749307,5.894,5.830
```
- `x_m, y_m` — smoothed centerline in TUMFTM real-world meters
- `w_tr_right_m` — track width to the right of centerline (direction of travel)
- `w_tr_left_m` — track width to the left of centerline

### Mapping session tracks → TUMFTM CSVs

| Sim track name | TUMFTM CSV | Notes |
|---|---|---|
| Circuit de Spa-Francorchamps | `Spa.csv` | Already aligned |
| Circuit de Barcelona | `Catalunya.csv` | Auto-aligned, needs visual QA |
| Autodromo Enzo e Dino Ferrari | — | **No TUMFTM data** |
| Fuji Speedway | — | **No TUMFTM data** |

---

## 3. Step-by-step pipeline (reproducible)

### Step 0: Prerequisites

```bash
# Verify npm dependencies
npm ls hyparquet hyparquet-compressors

# Download TUMFTM CSVs to /private/tmp/tumftm/
mkdir -p /private/tmp/tumftm
curl -sL "https://raw.githubusercontent.com/TUMFTM/racetrack-database/master/tracks/Spa.csv" -o /private/tmp/tumftm/Spa.csv
curl -sL "https://raw.githubusercontent.com/TUMFTM/racetrack-database/master/tracks/Catalunya.csv" -o /private/tmp/tumftm/Catalunya.csv
# Add more as needed
```

### Step 1: Identify unique session tracks

```bash
# List session JSON files and extract track names
ls sessions/*.json | grep -v apex-annotations | while read f; do
  python3 -c "import json; print(json.load(open('$f')).get('track','?'))"
done | sort -u
```

### Step 2: Convert TUMFTM CSV → JSON for the alignment tool

```bash
node scripts/prepare_manual_outline_inputs.js \
  --tumftm-csv /private/tmp/tumftm/Catalunya.csv \
  --tumftm-json data/track-outlines/alignment-artifacts/circuit-de-barcelona/tumftm-circuit-de-barcelona.json
```

### Step 3: Extract a reference lap trajectory from a session parquet

Pick a session with multiple completed laps (check `lap_count` in the session JSON). Lap numbers from parquet are 1-indexed but may start at a high number if there were out-laps.

```bash
# Pick a good Barcelona session (e.g. session_20260514T141305Z with 8 laps)
# First check available lap numbers:
node -e "
const { exportTrajectories } = require('./scripts/prepare_manual_outline_inputs.js');
exportTrajectories(['sessions/session_20260514T141305Z_circuit-de-barcelona_lmu.parquet'], '/dev/null', { stride: 5 })
  .then(d => d.trajectories.forEach(t => console.log(t.name, ':', t.points.length, 'pts')))
"
```

```bash
# Export a reference lap trajectory
node scripts/prepare_manual_outline_inputs.js \
  --trajectory-json data/track-outlines/alignment-artifacts/circuit-de-barcelona/trajectory-circuit-de-barcelona.json \
  --lap 1 \
  --stride 5 \
  sessions/session_20260514T141305Z_circuit-de-barcelona_lmu.parquet
```

Note: `stride` downsamples. For alignment, stride 5 gives ~1-2k points which is dense enough. For the manual tool, stride 10–20 renders faster. The alignment quality is NOT affected by stride (ICP resamples internally).

### Step 4: Run automated initial alignment (ICP)

This finds a coarse similarity transform (scale, rotation, translation, optional flips) by iterative closest point. It tries all 8 combinations of flip_x, flip_y, and reverse point order.

```bash
node scripts/auto_align_outline.js \
  --tumftm-json data/track-outlines/alignment-artifacts/circuit-de-barcelona/tumftm-circuit-de-barcelona.json \
  --trajectory-json data/track-outlines/alignment-artifacts/circuit-de-barcelona/trajectory-circuit-de-barcelona.json \
  --sim-track-name "Circuit de Barcelona" \
  --try-all-flips \
  --out data/track-outlines/circuit-de-barcelona.json
```

**Or use the all-tracks orchestrator:**

```bash
node scripts/prepare_all_outlines.js
```

This script:
1. Converts TUMFTM CSVs configured in `TRACKS` to JSON
2. Extracts reference trajectories from configured session files
3. Runs ICP with all flip/reverse combos
4. Writes outline JSON to `data/track-outlines/<slug>.json`
5. Writes intermediate artifacts to `data/track-outlines/alignment-artifacts/<slug>/`

To add a new track, edit the `TRACKS` object in `scripts/prepare_all_outlines.js`.

### Step 5: Visual QA with the manual alignment tool

**This step requires a human with eyes.** The automated alignment is coarse and MUST be visually verified.

```bash
# Open the manual alignment tool in a browser
open tools/manual_outline_align.html
```

Then:
1. Load the trajectory JSON (Step 3 output) as "Simulator reference trajectory"
2. Load the TUMFTM JSON (Step 2 output) as "TUMFTM track"
3. Check that the auto-aligned boundaries roughly match — adjust if needed
4. Export the aligned outline JSON
5. Replace the file in `data/track-outlines/`

Intermediate artifacts live in `data/track-outlines/alignment-artifacts/<slug>/`:
- `tumftm-<slug>.json` — TUMFTM source data
- `trajectory-<slug>.json` — simulator reference trajectory

Keyboard shortcuts in the tool:
- Arrow keys: translate (shift for bigger steps)
- Q/E: rotate
- +/-: scale
- F: cycle flip combinations
- R: reverse point order

### Step 6: Generate the static outline ES module for the frontend

```bash
node scripts/generate_outline_module.js data/track-outlines/circuit-de-barcelona.json
# → writes web/js/staticCircuitBarcelonaOutlineData.js
```

### Step 7: Wire the outline into the track manifest

Edit `web/js/trackOutlineManifest.js`:
1. Import the new static outline data module
2. Add entries to the `OUTLINES` map with appropriate slug keys

The outline is now used automatically when a session with the matching track name is loaded.
No changes needed in `trackHeatmapMap.js` or `circuitMap.js` — they already import from the manifest.

### Step 8: Verify

```bash
# Run tests
bash scripts/test-summary.sh

# Build and check
npm run build
```

---

## 4. Scripts inventory

| Script | Purpose |
|---|---|
| `scripts/prepare_manual_outline_inputs.js` | Convert TUMFTM CSV→JSON; extract trajectory from parquet |
| `scripts/auto_align_outline.js` | ICP-based automated alignment; exports `runICP`, `generateOutline` |
| `scripts/prepare_all_outlines.js` | Orchestrate: convert, extract, align for all configured tracks |
| `scripts/generate_outline_module.js` | Generate `web/js/static*OutlineData.js` from outline JSON |
| `tools/manual_outline_align.html` | Visual alignment tool for human QA / refinement |

---

## 5. Outline JSON schema (v1)

```json
{
  "schema_version": 1,
  "source": "TUMFTM manual alignment",
  "track_name": "Circuit de Barcelona-Catalunya",
  "sim_track_name": "Circuit de Barcelona",
  "layout_name": "default",
  "coordinate_system": "sim_xy",
  "units": "sim_units",
  "track_name_mapping": {
    "canonical_sim_track_name": "circuit-de-barcelona",
    "canonical_lmu_track_name": "Circuit de Barcelona-Catalunya",
    "accepted_sim_track_names": ["circuit-de-barcelona"],
    "accepted_lmu_track_names": ["Circuit de Barcelona"],
    "notes": "..."
  },
  "alignment": {
    "method": "manual_similarity_transform",
    "scale": 1.0064,
    "rotation_rad": 0.0017,
    "translate_x": 179,
    "translate_y": 253,
    "flip_x": false,
    "flip_y": false,
    "reverse_point_order": true,
    "notes": "..."
  },
  "visual_qa": { "status": "pending", "notes": "..." },
  "caveats": ["..."],
  "centerline": [{ "x": ..., "y": ... }],
  "left_boundary": [{ "x": ..., "y": ... }],
  "right_boundary": [{ "x": ..., "y": ... }]
}
```

All coordinate arrays are in **simulator coordinates** (same frame as `pos_x_m`/`pos_z_m` from parquet). The frontend does not need to know about TUMFTM coordinate frames.

---

## 6. Key coordinate mapping

The simulator uses `pos_x_m` as X and `pos_z_m` as Y (the track map's vertical axis). In pipeline code these appear as `currentTrackX` / `currentTrackZ`. The outline JSON uses `{ x, y }` which maps to `{ pos_x_m, pos_z_m }`.

---

## 7. Frontend track outline architecture

- **`web/js/trackOutlineManifest.js`** — maps slugified track names to outline data via `findOutlineByTrackName(trackName)`. Returns `null` for unknown tracks (app still works, just no outline shown).
- **`web/js/staticTrackOutline.js`** — validation + rendering functions (`drawStaticTrackOutline`, `renderStaticTrackOutlineSvg`)
- **`web/js/static*OutlineData.js`** — generated ES modules containing inline outline data
- **`web/js/main.js`** — sets `currentTrackName` from `sessionEntry.sidecar.track`, falls back to filename inference via `inferTrackNameFromFileName()`
- **`web/js/trackHeatmapMap.js`** — calls `findOutlineByTrackName(trackName)` and draws outline if found
- **`web/js/circuitMap.js`** — same for SVG rendering path

---

## 8. Spa Endurance note

"Circuit de Spa-Francorchamps Endurance" uses the **same coordinate system** as regular "Circuit de Spa-Francorchamps" in LMU (verified: both sessions produce X ranges -562 to +702, Y ranges -1060 to +1001). The existing Spa outline covers both via aliases in the manifest. No separate outline file is needed unless the layout visibly differs (e.g. Bus Stop chicane variant).

---

## 9. Known gaps

- **Imola (autodromo-enzo-e-dino-ferrari):** No TUMFTM CSV. TUMFTM database has no Imola data. Would need alternative data source or hand-drawn outline.
- **Fuji Speedway:** No TUMFTM CSV. Same issue.
- **Auto-alignment quality:** ICP produces a coarse alignment (mean error ~6 sim-units for Barcelona). Visual QA in the manual tool is essential. The centerline is the geometric center; the sim trajectory is the racing line, so expect 5-15 sim-unit deviations at corners where drivers clip the apex.