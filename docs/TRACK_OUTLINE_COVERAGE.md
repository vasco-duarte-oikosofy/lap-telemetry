# Track Outline Coverage

## Outline types

### Real outline (TUMFTM-aligned)
Boundaries come from the TUMFTM racetrack database, which provides per-point
track widths (`w_tr_right_m`, `w_tr_left_m`). The left and right boundaries
are offset from the centerline by **varying distances**, reflecting actual
track width changes (chicanes wider, narrow sections tighter).

This enables **apex proximity analysis** — the boundary tells you how far the
driver's line is from the actual track edge at each point.

### Trajectory outline (session-data-only)
When no TUMFTM data is available, the outline is generated from a single fast
lap (or median of fastest laps). The centerline is the driving line, and
boundaries are computed by inflating the centerline with a **constant width**
(e.g. 5m on each side). The boundary is a uniform shell around the racing
line — it does not reflect real track edges.

**Limitation:** Because the boundary is equidistant from the driving line, the
driver always appears to be exactly in the center of the track. Apex proximity
analysis is meaningless — you can't tell if the driver is close to the inside
kerb or far from the outside wall.

---

## Current coverage

| Track | Session slug | Outline type | Source | Width data | Apex-ready |
|-------|-------------|-------------|--------|-----------|------------|
| Circuit de Spa-Francorchamps | `circuit-de-spa-francorchamps` | **Real** | TUMFTM `Spa.csv` | Varies per point (3.9–8.6m left, 4.8–7.3m right) | ✅ Yes |
| Circuit de Spa-Francorchamps Endurance | `circuit-de-spa-francorchamps-endurance` | **Real** | Same Spa outline | Same | ✅ Yes |
| Circuit de Barcelona-Catalunya | `circuit-de-barcelona` | Trajectory | Median of 5 fastest laps | Constant 5m each side | ❌ No |
| Bahrain International Circuit | `bahrain-international-circuit` | **Real** | TUMFTM `Sakhir.csv` | Varies per point | ✅ Yes |
| Fuji Speedway | `fuji-speedway` | Trajectory | Single lap (lap 14, 1:38.097, 2026-06-07) | Constant 5m each side | ❌ No |
| Autodromo Enzo e Dino Ferrari | `autodromo-enzo-e-dino-ferrari` | ❌ None | — | — | — |
| Lusail International Circuit | `lusail-international-circuit` | Trajectory | Single lap (lap 12, 1:52.200, 2026-05-22) | Constant 5m each side | ❌ No |
| Fuji Speedway Classic | `fuji-speedway-classic` | Trajectory | Single lap (lap 3, 1:38.541, 2026-06-06) | Constant 5m each side | ❌ No |
| Sebring International Raceway | `sebring-international-raceway` | Trajectory | Single lap (lap 3, 2:04.384, 2026-06-07) | Constant 5m each side | ❌ No |
| Circuit de la Sarthe | `circuit-de-la-sarthe` | Trajectory | Single lap (lap 3, 3:50.650, 2026-06-14) | Constant 5m each side | ❌ No |

---

## How to tell which type an outline is

| Property | Real outline | Trajectory outline |
|----------|-------------|-------------------|
| `source` field | `TUMFTM manual alignment` | `Single lap trajectory` or `Median trajectory` |
| Boundary offset from centerline | Varies per point | Constant offset |
| Left/right width range | > 0 (e.g. 3.9–8.6m) | 0 (exact constant) |
| Apex proximity meaningful | ✅ Yes | ❌ No |
| Centerline = | TUMFTM geometric center | Driving/racing line |

---

## Path to real outlines

### Tier 1: TUMFTM data available (best quality — centerline + real widths)

| Track | TUMFTM CSV | Status |
|-------|-----------|--------|
| Circuit de Spa-Francorchamps | `Spa.csv` | ✅ Done |
| Bahrain International Circuit | `Sakhir.csv` | ✅ Done |
| Autódromo José Carlos Pace (Interlagos) | `SaoPaulo.csv` | No session data yet |
| Autodromo Nazionale Monza | `Monza.csv` | No session data yet |
| Circuit of the Americas | `Austin.csv` | No session data yet |

**Bahrain** is the immediate win — already has sessions and a TUMFTM CSV.

### Tier 2: bacinger/f1-circuits available (centerline only — needs width estimation)

| Track | bacinger GeoJSON | Missing |
|-------|-----------------|---------|
| Autodromo Enzo e Dino Ferrari (Imola) | `it-1953` | No widths |
| Circuit de Barcelona-Catalunya | `es-1991` | No widths (TUMFTM `Catalunya.csv` is wrong layout) |

**Width estimation approaches:**
1. **Constant width per track** — simple, same as current trajectory outlines
2. **Per-corner heuristic** — wider at hairpins, narrower at fast curves
3. **OSM way width tags** — extract from OpenStreetMap `width` tag if available
4. **Multi-lap spread estimation** — use the spread of driving lines across many laps to estimate minimum width (underestimates full width)

### Tier 3: No existing data source (needs OSM extraction or hand-drawn)

| Track | Options |
|-------|---------|
| Fuji Speedway | ✅ Trajectory outline done; OSM extraction needed for real widths |
| Fuji Speedway Classic | ✅ Trajectory outline done; OSM extraction needed for real widths |
| Circuit de la Sarthe (Le Mans) | ✅ Trajectory outline done; OSM extraction needed for real widths |
| Lusail International Circuit | ✅ Trajectory outline done; OSM extraction needed for real widths |
| Sebring International Raceway | ✅ Trajectory outline done; OSM or satellite imagery for real widths |

---

## Recommended upgrade order

1. ~~**Bahrain**~~ — ✅ Done. TUMFTM `Sakhir.csv` aligned.
2. **Imola** — Most requested LMU track without a real outline. Use bacinger centerline + width estimation. Needs new alignment pipeline step for lon/lat → sim coordinate conversion.
3. **Barcelona** — Upgrade to real boundaries. The TUMFTM `Catalunya.csv` is the **old F1 layout**, not the MotoGP/chicane layout used in LMU. Either find correct-layout data or use bacinger + width estimation.
4. **Fuji** — No automated data source. OSM extraction or hand-drawn only.

---

## Alternative data sources

| Source | Data | License | Tracks |
|--------|------|---------|--------|
| [TUMFTM racetrack-database](https://github.com/TUMFTM/racetrack-database) | Centerline + per-point widths | LGPL-3.0 | 24 tracks |
| [bacinger/f1-circuits](https://github.com/bacinger/f1-circuits) | Centerline (lon/lat) | MIT | ~40 F1 circuits |
| [lovely-track-data](https://github.com/Lovely-Sim-Racing/lovely-track-data) | Turn metadata only (no coordinates) | — | Imola, Fuji, Barcelona |
| OpenStreetMap | Centerline (`highway=raceway`), sometimes `width` tag | ODbL | Many |
| LMU session trajectories | Racing line (too narrow for boundaries) | — | All tracks with sessions |