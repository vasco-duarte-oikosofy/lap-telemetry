# Handoff — Slice 13 (Monza Curva Grande Circuit)

## What is on disk now

**Reference lap** (guarded export; fastest valid lap of the only session on disk):
- `product/data/reference-laps/monza-curva-grande-circuit_dkr-engineering-4-elms25_time_01.35.182.parquet`
- Source: `sessions/session_20261031T065746Z_monza-curva-grande-circuit_lmu_practice.parquet`,
  lap 12 @ 1:35.182 (4739 rows).
- `AUDIT: 1 reference lap changed (added ...). OK.` — nothing else in the folder moved.
- `validate_reference_laps.py`: 31 laps checked, 0 failures.

**Coaching model** (generated, then hand-curated: names, flat corners, apex sides):
- `product/data/track-coaching/monza-curva-grande-circuit_dkr-engineering-4-elms25.json`
- `...diagnostics.txt` (raw detector output — 5 braking corners, unrenamed)
- 10 corners, official Monza names, in lap order:

| id | name | start | apex | end | side | flat |
|---|---|---|---|---|---|---|
| t1 | Curva Grande | 1170 | 1400 | 1795 | right | `target_throttle_pct: 100` |
| t2 | Variante della Roggia 1 | 1930 | 2109 | 2130 | left | |
| t3 | Variante della Roggia 2 | 2131 | 2153 | 2209 | right | |
| t4 | Lesmo 1 | 2402 | 2521 | 2531 | right | |
| t5 | Lesmo 2 | 2740 | 2833 | 2855 | right | |
| t6 | Curva del Serraglio | 3150 | 3240 | 3400 | left | `target_throttle_pct: 100` |
| t7 | Variante Ascari 1 | 3766 | 3910 | 3953 | left | |
| t8 | Variante Ascari 2 | 3954 | 4006 | 4062 | right | |
| t9 | Variante Ascari 3 | 4064 | 4104 | 4238 | left | |
| t10 | Curva Alboreto (Parabolica) | 4962 | 5128 | 5138 | right | |

**Track outline** (trajectory; no TUMFTM CSV exists for this layout):
- `product/data/track-outlines/monza-curva-grande-circuit.json` (500 pts, closed to 0.9 m)
- ES module `product/web/js/staticMonzaCurvaGrandeCircuitOutlineData.js`
- `product/web/js/trackOutlineManifest.js`: import + `['monza-curva-grande-circuit', …]`
  (also written by `register_outline.py` into `trackOutlineManifest_backup.js`)
- `product/dist/compare.html` rebuilt via `npm run build` (the auto-build inside
  `register_outline.py` fails on Windows — `FileNotFoundError [WinError 2]` on
  the subprocess; documented, run the npm script manually).
- `docs/TRACK_OUTLINE_COVERAGE.md`: coverage row + Tier 3 entry.

## Naming decisions (why the model does not say "turn 1")

- This layout **has no Variante del Rettifilo**. It is full Monza (5742 m vs
  5790 m) with the T1/T2 chicane removed, so the main straight runs into
  Curva Grande, which is now **flat in 6th** (~287 kph, throttle 1.00).
- `Curva Grande` is officially **Curva Biassono** (renamed 1972); `Curva
  Alboreto (Parabolica)` is the 2021 renaming. Both spellings are in use, so the
  model uses the widely-used name with the official alias where they differ.
- Official 10-turn counting for this layout: Curva Grande, Roggia ×2, Lesmo ×2,
  Serraglio, Ascari ×3, Parabolica. Full Monza is listed as 11 because the
  Rettifilo chicane counts as two; dropping it (−2) and adding the Serraglio
  (+1) gives the 10 that LMU/RaceCenter list for this layout.
- The model splits the chicanes into their constituent turns (Roggia 1/2,
  Ascari 1/2/3) because those are the official sub-turn names (Monza even names
  grandstands "Ascari Uno/Due/Tre"). The detector only sees one merged braking
  event per chicane.

## How the geometry was derived

`steering_norm` alone is not enough for the flat turns (max |steer| 0.03–0.09),
so apex sides and flat-corner apexes come from **position curvature**
(`pos_x_m`/`pos_z_m`, ±0.5 s three-point circle after smoothing), calibrated
against two known corners: Lesmo 1 (right) and Roggia 1 (left). Sign convention
found on this lap: curvature **negative = right**, `steering_norm` **positive =
right** (the two disagree in sign, which is expected).

Curvature check of the two flat turns, matching the official circuit description:

| corner | measured min radius | official |
|---|---|---|
| Curva Grande | 317 m @ 1399 m | "right of about 300 m, taken in full" |
| Curva del Serraglio | ~1050 m @ 3240 m | "very slight left, radius over 600 m" |

Zone convention used here: entry = brake onset (braking corners) or bend start
(flat corners); exit = brake release (braking corners) or the point curvature
returns above a 2500 m radius (flat corners).

## Layout verification (strong, cheap check)

Overlay of the new trajectory outline on the existing TUMFTM-aligned
`autodromo-nazionale-monza.json` centreline: **median 3.3 m, p90 5.0 m**, max
38.8 m — and the >25 m points are exactly five consecutive samples around
~970 m, i.e. the absent Rettifilo chicane. That confirms both the geometry and
the "full Monza minus the first chicane" reading of the layout.

Resolver checks (`resolve_reference_lap` / `resolve_track_model`):
- `"Monza Curva Grande Circuit"` → the new ref + model.
- `"Autodromo Nazionale Monza"` → still the 1:45.828 ref + chicane-layout model.
- `findOutlineByTrackName` resolves both, to different outline objects.

## Verification run

```
lap-telemetry summary <session>                      # lap 12 = 1:35.182, all 15 laps valid
extract_reference_lap.py --lap 10 -> var/tmp/...     # 1:35.748 comparison lap
generate_utterance --lap ... --print-facts           # delta +0.566 s, every corner id resolved
```

`--print-facts` reported losses at "Variante della Roggia 2" (0.324 s,
apex 13 m late) and "Curva Alboreto (Parabolica)" exit — plausible for a lap
0.57 s off the reference, and all names come out of the model (no KeyError).

## Deferred / open

- **Visual QA (the mission's second slice for every track) is NOT done.** The
  outline resolves and the Playwright outline probe passes, but nobody has
  looked at Monza Curva Grande rendering on the map.
- Only the **practice** session exists for this combo. A quali/race lap would
  probably beat 1:35.182 and should go through
  `update_reference_and_coaching_model.py` (Pipeline B) — the flat corners are
  >600 m from any braking apex, so bug 29's greedy-match hazard does not apply
  here.
- `TRACK_OUTLINE_COVERAGE.md` still says "Autodromo Nazionale Monza —
  `Monza.csv` — No session data yet" in the Tier 1 table. Pre-existing
  staleness (Monza is done); not touched by this slice.
- No `track-outline` key in `package.json` `testFeatures`; this mission still
  has no feature test list. Outline tests were run ad hoc (see learnings).
