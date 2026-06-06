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

No changes needed in `trackHeatmapMap.js` or `circuitMap.js` — they already import from the manifest.

**Important:** `web/compare.html` imports modules directly and will pick up the change immediately. `dist/compare.html` is a pre-built bundle and will NOT reflect the new outline until you run the build in step 8.

### Step 8: Build and verify

```bash
# Rebuild the distribution bundle — required for dist/compare.html to include the new outline
npm run build

# Run tests
bash scripts/test-summary.sh
```

Open `product/dist/compare.html`, load a session for the new track, and confirm the circuit map appears in the sidebar.

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

## 9. Data source coverage for LMU tracks

### Our session tracks and best available data sources

| Session slug | TUMFTM (best: centerline + widths) | bacinger/f1-circuits (centerline only, lon/lat) | Outline status |
|---|---|---|---|
| `circuit-de-spa-francorchamps` | Spa.csv ✅ | be-1925.geojson | ✅ Done |
| `circuit-de-spa-francorchamps-endurance` | Same as Spa | be-1925.geojson | ✅ Covered |
| `circuit-de-barcelona` | Catalunya.csv ⚠️ **wrong layout** | es-1991.geojson | ❌ Needs bacinger + width estimation |
| `autodromo-enzo-e-dino-ferrari` | ❌ not available | it-1953.geojson | ❌ Needs bacinger + width estimation |
| `fuji-speedway` | ❌ not available | ❌ not available | ❌ Needs OSM extraction |
| `spa-francorchamps` | Same as Spa | be-1925.geojson | ✅ Covered |

### Extended LMU coverage (all LMU tracks, for future sessions)

| LMU track | TUMFTM | bacinger | Needs |
|---|---|---|---|
| Autódromo Internacional do Algarve | ❌ | pt-2008 | bacinger + width estimation |
| Autodromo Enzo e Dino Ferrari (Imola) | ❌ | it-1953 | bacinger + width estimation |
| Autódromo José Carlos Pace (Interlagos) | SaoPaulo ✅ | br-1940 | TUMFTM ★ |
| Autodromo Nazionale Monza | Monza ✅ | it-1922 | TUMFTM ★ |
| Bahrain (all layouts) | Sakhir ✅ | bh-2002 | ✅ Done |
| Circuit de la Sarthe (Le Mans) | ❌ | ❌ | OSM extraction |
| Circuit de Spa-Francorchamps | Spa ✅ | be-1925 | ✅ Done |
| Circuit of the Americas | Austin ✅ | us-2012 | TUMFTM ★ |
| Fuji International Speedway | ❌ | ❌ | OSM extraction |
| Lusail International Circuit | ❌ | qa-2004 | bacinger + width estimation |
| Sebring International Raceway | ❌ | ❌ | OSM extraction |

**Summary:** 1 track done, 3 more ready for TUMFTM (once sessions exist), 4 have bacinger centerlines, 5 need OSM extraction.

### Alternative data sources explored

#### Lovely-Sim-Racing/lovely-track-data — ❌ metadata only
Has Imola, Fuji, Barcelona for LMU. But the data is **turn/sector metadata only** (turn names, percentage positions, direction, scale). No centerline coordinates, no widths, no boundary geometry. Cannot generate outlines from this.

#### LMU session trajectories — ❌ tested and useless
Tried deriving boundaries from the spread of driving lines across multiple laps. The racing line variation is far too narrow (a few meters at most) compared to full track width (~12m). This only gives you the racing corridor, not the track outline. Useless for this purpose.

#### bacinger/f1-circuits — 🟡 useful for centerlines
312 stars, MIT licensed. GeoJSON centerlines for ~40 F1 circuits in lat/lon (WGS84). No widths, no boundary data.
Repo: https://github.com/bacinger/f1-circuits
Interactive map: https://svemir.co/f1/

#### OpenStreetMap — next option for missing tracks
OSM has `highway=raceway` ways for Imola and Fuji. TUMFTM's own centerlines were extracted from OSM. Would give centerline GPS coordinates but no widths — widths must be estimated separately.

- **Imola (autodromo-enzo-e-dino-ferrari):** No TUMFTM CSV. TUMFTM database has no Imola data. Would need alternative data source or hand-drawn outline.
- **Fuji Speedway:** No TUMFTM CSV. Same issue.
- **Auto-alignment quality:** ICP produces a coarse alignment (mean error ~6 sim-units for Barcelona). Visual QA in the manual tool is essential. The centerline is the geometric center; the sim trajectory is the racing line, so expect 5-15 sim-unit deviations at corners where drivers clip the apex.