# Mission: Track Outline — All LMU Tracks

**Spec:** [`docs/TRACK_OUTLINE_COVERAGE.md`](../../docs/TRACK_OUTLINE_COVERAGE.md) and [`docs/specs/MULTI_TRACK_TUMFTM_OUTLINE_PIPELINE.md`](../../docs/specs/MULTI_TRACK_TUMFTM_OUTLINE_PIPELINE.md)

**Goal:** Every LMU track that has session data must have an outline JSON in `product/data/track-outlines/` and a corresponding ES module wired into the manifest. Tracks with TUMFTM data get real outlines (varying widths, apex-ready). Tracks without TUMFTM data get clean trajectory outlines (constant-width shells around the driving line).

**Data source policy:** TUMFTM when available, otherwise `source: clean trajectory`. No bacinger/f1-circuits data — their centerlines are in WGS84 lon/lat and lack width data, making them no better than trajectory outlines after alignment.

---

## Vertical slices

Each track is **two slices**: (1) ingest + generate the outline data + ES module, (2) visual QA — load the outline in the app and verify it renders correctly at the right scale and position on the map.

Tracks are ordered by data quality: TUMFTM first (real widths), then trajectory-only.

| Slice | Track | Data source | Type | Status |
|---|---|---|---|---|
| `01-spa` | Circuit de Spa-Francorchamps | TUMFTM `Spa.csv` | Real | ✅ Done |
| `02-spa-endurance` | Circuit de Spa-Francorchamps Endurance | Same Spa outline (alias) | Real (alias) | ✅ Done |
| `03-bahrain` | Bahrain International Circuit | TUMFTM `Sakhir.csv` | Real | ✅ Done |
| `04-barcelona` | Circuit de Barcelona-Catalunya | ❌ No TUMFTM (wrong layout) | Clean trajectory | 🔲 Not started |
| `05-monza` | Autodromo Nazionale Monza | TUMFTM `Monza.csv` | Real | 🔲 Not started |
| `06-interlagos` | Autódromo José Carlos Pace | TUMFTM `SaoPaulo.csv` | Real | 🔲 Not started |
| `07-cota` | Circuit of the Americas | TUMFTM `Austin.csv` | Real | 🔲 Not started |
| `08-imola` | Autodromo Enzo e Dino Ferrari | ❌ No TUMFTM | Clean trajectory | 🔲 Not started |
| `09-fuji` | Fuji Speedway | ❌ No TUMFTM | Clean trajectory | 🔲 Not started |

Spa and Bahrain are done. 04–07 use TUMFTM real data. 08–09 are trajectory-only.

### Barcelona note

TUMFTM `Catalunya.csv` is the old F1 layout (pre-2007 chicane). LMU uses the MotoGP/chicane layout. The auto-alignment pipeline will attempt ICP against this CSV — visual QA in slice 2 will determine if the layout mismatch is acceptable. If not, we fall back to a clean trajectory outline.

---

## Per-track slice template

### Slice N-a: Ingest pipeline for `<track-name>`

**Outcome.** `<slug>.json` exists in `product/data/track-outlines/`, and a generated ES module `static<Name>OutlineData.js` is imported and wired into `trackOutlineManifest.js`.

**Steps (TUMFTM tracks):**
1. Add the track entry to `TRACKS` in `dev/scripts/prepare_all_outlines.js`.
2. Run `node dev/scripts/prepare_all_outlines.js` to auto-align, or use `dev/scripts/auto_align_outline.js` manually.
3. Visual-check the output in `tools/manual_outline_align.html`. Adjust alignment if needed.
4. Run `node dev/scripts/generate_outline_module.js product/data/track-outlines/<slug>.json` to create the ES module.
5. Import the new module in `product/web/js/trackOutlineManifest.js` and add slug entries to the `OUTLINES` map.
6. Run `bash scripts/test-summary.sh` — must pass.
7. Run `npm run build` — `dist/compare.html` must be current.

**Steps (trajectory tracks):**
1. Generate a trajectory outline from session data (single fast lap or median of fastest laps).
2. Write the outline JSON with `source: "clean trajectory"` and constant-width boundaries.
3. Run `node dev/scripts/generate_outline_module.js` to create the ES module.
4. Import and wire into `trackOutlineManifest.js`.
5. Run `bash scripts/test-summary.sh` — must pass.
6. Run `npm run build` — must succeed.

### Slice N-b: Map render + scale QA for `<track-name>`

**Outcome.** Loading a session for the track in the browser renders the outline correctly on the map canvas — boundaries visible, correctly positioned, correct scale, no visual glitches.

**Steps:**
1. Launch `dist/compare.html` and load a session for the track.
2. Verify the outline appears behind the trajectory on the map canvas.
3. Check boundary alignment at known reference points (start/finish, major corners).
4. Verify the outline doesn't shift if the window is resized.
5. If TUMFTM-aligned, verify that left/right boundary widths vary (not constant).
6. If trajectory, verify the constant-width shell is visible but clearly synthetic.
7. Fix any rendering issues found.
8. Run `bash scripts/test-summary.sh` — must pass.
9. Run `npm run build` — must succeed.

---

## Track details

### 01-spa ✅ Done
- TUMFTM `Spa.csv` → real outline with varying widths
- Manifest entries: `circuit-de-spa-francorchamps`, `circuit-de-spa-francorchamps-endurance`, `spa-francorchamps`

### 02-spa-endurance ✅ Done
- Alias of Spa outline (same coordinate system, verified)

### 03-bahrain ✅ Done
- TUMFTM `Sakhir.csv` → real outline with varying widths
- Manifest entries: `bahrain-international-circuit`, `bahrain`

### 04-barcelona
- **No TUMFTM data.** TUMFTM `Catalunya.csv` is the old F1 layout (no chicane), which doesn't match the LMU MotoGP/chicane layout. Source will be `clean trajectory`.
- **Session data:** `circuit-de-barcelona` (multiple sessions exist)
- **Current state:** Has a trajectory outline (`circuit-de-barcelona.json` sourced from "Median trajectory from 5 fastest laps") — upgrade to a clean trajectory outline with consistent source labeling.
- **Manifest entries:** `circuit-de-barcelona`, `barcelona-catalunya`, `catalunya`

### 05-monza
- **TUMFTM CSV:** `Monza.csv` (243 points)
- **Session data:** Not yet available — user will create sessions
- **Manifest entries:** `autodromo-nazionale-monza`, `monza`

### 06-interlagos
- **TUMFTM CSV:** `SaoPaulo.csv`
- **Session data:** Not yet available — user will create sessions
- **Manifest entries:** `autodromo-jose-carlos-pace`, `interlagos`

### 07-cota
- **TUMFTM CSV:** `Austin.csv`
- **Session data:** Not yet available — user will create sessions
- **Manifest entries:** `circuit-of-the-americas`, `cota`

### 08-imola
- **No TUMFTM data.** Source will be `clean trajectory` (constant-width shell around the driving line).
- **Session data:** `autodromo-enzo-e-dino-ferrari` (multiple sessions exist)
- **Current state:** No outline file exists at all.
- **Manifest entries:** `autodromo-enzo-e-dino-ferrari`, `imola`

### 09-fuji
- **No TUMFTM data.** Source will be `clean trajectory`.
- **Session data:** `fuji-speedway` (1 session exists)
- **Current state:** Has a trajectory outline (`fuji-speedway_outline.json`, single lap lap 7, constant 3m each side).
- **Manifest entries:** `fuji-speedway`, `fuji`

---

## Future LMU tracks (not yet sliced — add sessions first)

These tracks appear in LMU but have no session data yet. They'll get slices once sessions are recorded.

| Track | TUMFTM CSV | Expected source |
|---|---|---|
| Autódromo Internacional do Algarve (Portimão) | ❌ | Clean trajectory |
| Circuit de la Sarthe (Le Mans) | ❌ | Clean trajectory |
| Lusail International Circuit | ❌ | Clean trajectory |
| Sebring International Raceway | ❌ | Clean trajectory |
| Hockenheimring | `Hockenheim.csv` ✅ | TUMFTM real |
| Silverstone | `Silverstone.csv` ✅ | TUMFTM real |
| Zandvoort | `Zandvoort.csv` ✅ | TUMFTM real |
| Spielberg (Red Bull Ring) | `Spielberg.csv` ✅ | TUMFTM real |
| Suzuka | `Suzuka.csv` ✅ | TUMFTM real |
| Shanghai | `Shanghai.csv` ✅ | TUMFTM real |
| Melbourne | `Melbourne.csv` ✅ | TUMFTM real |
| Budapest (Hungaroring) | `Budapest.csv` ✅ | TUMFTM real |
| Mexico City | `MexicoCity.csv` ✅ | TUMFTM real |
| Montreal | `Montreal.csv` ✅ | TUMFTM real |
| Yas Marina | `YasMarina.csv` ✅ | TUMFTM real |
| Sepang | `Sepang.csv` ✅ | TUMFTM real |
| Sochi | `Sochi.csv` ✅ | TUMFTM real |

---

## Out of scope

- **Barcelona layout mismatch** — TUMFTM `Catalunya.csv` is the wrong layout. If correct-layout TUMFTM-quality data is found in the future, Barcelona can be upgraded from trajectory to real outline.
- **Width estimation for trajectory-only tracks** — no per-corner width heuristics; constant width is acceptable.
- **OSM centerline extraction** — not used. Trajectory outlines from driving data are simpler and equally useful when TUMFTM is unavailable.
- **bacinger/f1-circuits** — explicitly excluded. WGS84 lon/lat requires coordinate transform, and no width data means it's no better than a trajectory outline.
- **Apex proximity analysis** for trajectory outlines — by definition not possible (constant offset).