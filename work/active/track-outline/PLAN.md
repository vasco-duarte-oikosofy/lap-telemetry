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
| `02-spa-endurance` | Spa Endurance Layout (62-car) | Same Spa outline (alias) | Real (alias) | ✅ Done |
| `03-bahrain-gp` | Bahrain International Circuit (GP) | TUMFTM `Sakhir.csv` | Real | ✅ Done |
| `04-barcelona` | Circuit de Barcelona-Catalunya | Trajectory | Clean trajectory | ✅ Done |
| `05-monza` | Monza (with chicanes) | TUMFTM `Monza.csv` | Real | ✅ Done |
| `06-interlagos` | Autódromo José Carlos Pace | TUMFTM `SaoPaulo.csv` | Real | ✅ Done |
| `07-cota-gp` | Circuit of the Americas (GP) | TUMFTM `Austin.csv` | Real | 🔲 Not started |
| `08-imola` | Autodromo Enzo e Dino Ferrari | No TUMFTM | Clean trajectory | ✅ Done (trajectory) |
| `09-fuji` | Fuji International Speedway | No TUMFTM | Clean trajectory | ✅ Done |
| `10-bahrain-endurance` | Bahrain International Endurance Circuit | No TUMFTM | Clean trajectory | 🔲 Not started |
| `11-bahrain-outer` | Bahrain International Outer Circuit | No TUMFTM | Clean trajectory | ✅ Done (`cbead00`) |
| `12-bahrain-paddock` | Bahrain International Paddock Circuit | No TUMFTM | Clean trajectory | 🔲 Not started |
| `13-monza-curva-grande` | Monza Curva Grande Layout | No TUMFTM | Clean trajectory | 🔲 Not started |
| `14-cota-national` | COTA National | No TUMFTM | Clean trajectory | 🔲 Not started |
| `15-le-mans` | Circuit de la Sarthe | No TUMFTM | Clean trajectory | 🔲 Not started |
| `16-le-mans-no-chicanes` | Circuit de la Sarthe Mulsanne No Chicanes | No TUMFTM | Clean trajectory | 🔲 Not started |
| `17-algarve` | Algarve International Circuit (Portimão) | No TUMFTM | Clean trajectory | 🔲 Not started |
| `18-algarve-elms` | Algarve International Circuit ELMS | Verify alias of Algarve base | ? | 🔲 Not started |
| `19-lusail` | Lusail International Circuit | No TUMFTM | Clean trajectory | 🔲 Not started |
| `20-lusail-short` | Lusail International Circuit Short | No TUMFTM | Clean trajectory | 🔲 Not started |
| `21-sebring` | Sebring International Raceway | No TUMFTM | Clean trajectory | 🔲 Not started |
| `22-sebring-school` | Sebring School Circuit | No TUMFTM | Clean trajectory | 🔲 Not started |
| `23-paul-ricard` | Circuit Paul Ricard (ELMS) | No TUMFTM | Clean trajectory | 🔲 Not started |
| `24-paul-ricard-1a` | Paul Ricard 1a | No TUMFTM | Clean trajectory | 🔲 Not started |
| `25-paul-ricard-1av2` | Paul Ricard 1av2 | No TUMFTM | Clean trajectory | 🔲 Not started |
| `26-paul-ricard-1av2-short` | Paul Ricard 1av2-short | No TUMFTM | Clean trajectory | 🔲 Not started |
| `27-paul-ricard-3a` | Paul Ricard 3a | No TUMFTM | Clean trajectory | 🔲 Not started |
| `28-silverstone-elms` | Silverstone (ELMS Pack 1) | TUMFTM `Silverstone.csv` | Real | 🔲 Not started |
| `29-silverstone-national` | Silverstone National | No TUMFTM | Clean trajectory | 🔲 Not started |
| `30-silverstone-international` | Silverstone International | No TUMFTM | Clean trajectory | 🔲 Not started |
| `31-silverstone-gp-wec` | Silverstone GP (WEC) | No TUMFTM (verify vs base) | ? | 🔲 Not started |
| `32-fuji-classic` | Fuji Classic Layout (No Chicane) | No TUMFTM | Clean trajectory | 🔲 Not started |
| `33-imola-elms` | Imola ELMS | Verify alias of Imola base | ? | 🔲 Not started |

**Completed:** Spa (base + endurance), Bahrain GP, Barcelona, Monza, Imola, Fuji International Speedway, Bahrain Outer.
**In progress:** None.
**Remaining:** 26 outlines needed (some may be aliases).

### Barcelona note

TUMFTM `Catalunya.csv` is the old F1 layout (pre-2007 chicane). LMU uses the MotoGP/chicane layout. Visual QA confirmed the mismatch — Barcelona uses a trajectory outline instead.

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
6. **Run `npm run build`** — `dist/compare.html` is a pre-built bundle and will NOT show the new outline until rebuilt.
7. Run `bash scripts/test-summary.sh` — must pass.

**Steps (trajectory tracks):**
1. Generate a trajectory outline from session data (single fast lap or median of fastest laps).
2. Write the outline JSON with `source: "clean trajectory"` and constant-width boundaries.
3. Run `node dev/scripts/generate_outline_module.js` to create the ES module.
4. Import and wire into `trackOutlineManifest.js`.
5. **Run `npm run build`** — `dist/compare.html` will not reflect the change until rebuilt.
6. Run `bash scripts/test-summary.sh` — must pass.

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

Canonical track list source: Le Mans Ultimate full track + layout catalogue.
Each layout needs its own outline unless it's a confirmed alias (same physical track, same coordinate system).

---

### ✅ Completed outlines

#### Spa-Francorchamps ✅ Done
- **Layouts:** Spa-Francorchamps (base), Spa Endurance Layout (62-car support)
- **TUMFTM CSV:** `Spa.csv` → real outline with varying widths
- **Endurance is an alias** — same coordinate system, same outline, different name
- **Manifest entries:** `circuit-de-spa-francorchamps`, `circuit-de-spa-francorchamps-endurance`, `spa-francorchamps`

#### Bahrain International Circuit ✅ Done (GP layout only)
- **Layout done:** Bahrain International Circuit (GP layout)
- **TUMFTM CSV:** `Sakhir.csv` → real outline with varying widths
- **Manifest entries:** `bahrain-international-circuit`, `bahrain`
- **Remaining layouts** (separate outlines needed):
  - Bahrain International Endurance Circuit 🔲
  - Bahrain International Outer Circuit ✅ (`cbead00`)
  - Bahrain International Paddock Circuit 🔲

#### Circuit de Barcelona-Catalunya ✅ Done (trajectory)
- **No TUMFTM data.** TUMFTM `Catalunya.csv` is the old F1 layout (no chicane), which doesn't match the LMU MotoGP/chicane layout. Source: clean trajectory.
- **Session data:** `circuit-de-barcelona` (multiple sessions exist)
- **Outline:** `circuit-de-barcelona.json` — median trajectory from 2 exported laps, 500-point centerline, ±5m constant-width boundaries.
- **Manifest entries:** `circuit-de-barcelona`, `barcelona-catalunya`, `catalunya`
- **ES module:** `staticCircuitBarcelonaOutlineData.js`

#### Autodromo Enzo e Dino Ferrari (Imola) ✅ Done (trajectory)
- **No TUMFTM data.** Source: clean trajectory
- **Session data:** `autodromo-enzo-e-dino-ferrari` (5 sessions exist)
- **Outline:** `autodromo-enzo-e-dino-ferrari.json` — median trajectory from 2 copies of lap 11 (101.42s), 500-point centerline, ±5m constant-width boundaries
- **Manifest entries:** `autodromo-enzo-e-dino-ferrari`, `imola`
- **ES module:** `staticAutodromoDinoFerrariOutlineData.js`
- **Remaining layout** (separate outline needed):
  - Imola ELMS 🔲 (may be alias of base — verify with session data)

#### Fuji International Speedway ✅ Done (trajectory)
- **No TUMFTM data.** Source: clean trajectory (constant-width shell around the driving line).
- **Session data:** `fuji-speedway` (1 session exists)
- **Outline:** `fuji-speedway_outline.json` — single-lap trajectory outline (lap 7), constant 3m each side.
- **Manifest entries:** `fuji-speedway`, `fuji`
- **Remaining layout** (separate outline needed):
  - Fuji Classic Layout (No Chicane) 🔲

---

### 🔲 Remaining LMU tracks and layouts

#### Monza ✅ Done
- **Layouts needing outlines:**
  - Monza (base, with chicanes) — TUMFTM `Monza.csv` aligned and visual QA complete ✅
  - Monza Curva Grande Layout — ❌ no TUMFTM separate CSV (different layout)
- **TUMFTM CSV:** `Monza.csv` → 1159 points with varying widths (5.7–5.9m)
- **ICP alignment:** scale=0.9994 rot=−0.07° tx=−308 ty=−458 mean error 4.37 sim-units (no flips needed)
- **Alignment artifacts:** `product/data/track-outlines/alignment-artifacts/autodromo-nazionale-monza/`
- **Outline:** `autodromo-nazionale-monza.json` — TUMFTM real boundaries (was previously trajectory-only ±5m)
- **ES module:** `staticAutodromoNazionaleMonzaOutlineData.js` (163 KB)
- **Manifest entries:** `autodromo-nazionale-monza`, `monza`
- **Session data:** Using exported lap from reference-lap parquet
- **Visual QA:** Done — boundaries verified around the sim trajectory at main straight, chicanes, and Parabolica

#### Autódromo José Carlos Pace (Interlagos) ✅ Done
- **Layouts:** base only
- **TUMFTM CSV:** `SaoPaulo.csv` (862 points)
- **Session data:** `session_20260606T064918Z_autdromo-jos-carlos-pace_lmu_practice` (22 laps)
- **Reference lap:** lap 19, 1:31.770, `autdromo-jos-carlos-pace_dkr-engineering-4-elms25_time_01.31.770.parquet`
- **Outline:** `autodromo-jose-carlos-pace.json` — TUMFTM real boundaries, manually aligned
- **ES module:** `staticAutodromoJoseCarlosPaceOutlineData.js` (121 KB)
- **Manifest entries:** `autdromo-jos-carlos-pace` (slugify result from sim track name), `interlagos`
- **Note:** Recorder strips accented chars from "Autódromo José Carlos Pace" → slug `autdromo-jos-carlos-pace`

#### Circuit of the Americas 🔲
- **Layouts needing outlines:**
  - Circuit of the Americas (GP) — TUMFTM `Austin.csv` available
  - COTA National — ❌ no TUMFTM separate CSV (different layout)
- **Session data:** Not yet available (2024 Pack 2 DLC)
- **Manifest entries:** `circuit-of-the-americas`, `cota`, ?

#### Autodromo Internazionale Enzo e Dino Ferrari (Imola) ✅ Done (trajectory)
- See completed section above

#### Circuit de la Sarthe (Le Mans) 🔲
- **Layouts:** base + Mulsanne No Chicanes
- **No TUMFTM data.** Source: clean trajectory
- **Session data:** Not yet available
- **Manifest entries:** `circuit-de-la-sarthe`, ?

#### Algarve International Circuit (Portimão) 🔲
- **Layouts:** base + ELMS (may be same physical layout — verify)
- **No TUMFTM data.** Source: clean trajectory
- **Session data:** Not yet available
- **Manifest entries:** `algarve-international-circuit`, `portimao`, ?

#### Lusail International Circuit 🔲
- **Layouts:** base + Short
- **No TUMFTM data.** Source: clean trajectory
- **Session data:** Not yet available (2024 Pack 5 DLC)
- **Manifest entries:** `lusail-international-circuit`, ?

#### Sebring 🔲
- **Layouts:** base + School Circuit
- **No TUMFTM data.** Source: clean trajectory
- **Session data:** Not yet available
- **Manifest entries:** `sebring`, ?

#### Circuit Paul Ricard 🔲
- **Layouts:** base (ELMS) + 1a + 1av2 + 1av2-short + 3a
- **No TUMFTM data.** Source: clean trajectory
- **Session data:** Not yet available (ELMS Pack 2 DLC)
- **Manifest entries:** `circuit-paul-ricard`, ?

#### Silverstone 🔲
- **Layouts:** base (ELMS Pack 1) + National + International + GP (WEC)
- **TUMFTM CSV:** `Silverstone.csv` (likely GP layout only)
- **Session data:** Not yet available
- **Manifest entries:** `silverstone`, ?

---

### 📋 Layout alias rules

Some LMU "extra layouts" share the same physical track geometry and can reuse the same outline as an alias:

| Layout | Alias of | Reason |
|--------|----------|--------|
| Spa Endurance Layout (62-car support) | Spa-Francorchamps | Same track, same coords, verified |
| Autodromo Enzo e Dino Ferrari ELMS | Imola base | Likely same layout — **verify with session data** |
| Algarve ELMS | Algarve base | Likely same layout — **verify with session data** |

Other "extra layouts" are **genuinely different track configurations** and need separate outlines:

| Layout | Why different |
|--------|-------------|
| Bahrain Endurance / Outer / Paddock | Shorter/different loop configurations |
| Monza Curva Grande Layout | No chicane on main straight — different outline |
| COTA National | Shorter layout — different outline |
| Fuji Classic Layout (No Chicane) | No chicane — different outline |
| Le Mans Mulsanne No Chicanes | No chicanes on Mulsanne straight — different outline |
| Lusail Short | Shorter layout — different outline |
| Sebring School Circuit | Shorter layout — different outline |
| Silverstone National / International / GP (WEC) | Different configurations |
| Paul Ricard 1a / 1av2 / 1av2-short / 3a | Different configurations |

---

## Out of scope

- **Barcelona layout mismatch** — TUMFTM `Catalunya.csv` is the wrong layout. If correct-layout TUMFTM-quality data is found in the future, Barcelona can be upgraded from trajectory to real outline.
- **Width estimation for trajectory-only tracks** — no per-corner width heuristics; constant width is acceptable.
- **OSM centerline extraction** — not used. Trajectory outlines from driving data are simpler and equally useful when TUMFTM is unavailable.
- **bacinger/f1-circuits** — explicitly excluded. WGS84 lon/lat requires coordinate transform, and no width data means it's no better than a trajectory outline.
- **Apex proximity analysis** for trajectory outlines — by definition not possible (constant offset).
- **Non-LMU tracks** — only tracks that appear in Le Mans Ultimate are in scope.
- **DLC tracks not yet released** — will be added as they become available.