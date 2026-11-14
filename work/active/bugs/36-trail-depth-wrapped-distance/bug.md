# Bug 36 — `trail_brake_depth_m` returns the window length on any lap whose distance axis wraps

## Symptom

Circuit de Barcelona race, Ginetta LMP3
(`sessions/session_20261113T184458Z_circuit-de-barcelona_lmu_race.parquet`, 2026-11-13),
the debrief's number-1 priority:

```
Repsol — 0.264 s per lap (every lap, and erratic, 16% of the gap)
hold the brake 44 m longer and carry 4 km/h more speed onto the straight
```

There is no 44 m of brake to hold. Measured in distance order, the driver
releases within **1 m** of the apex on every lap in the session, and the
reference releases **0.17 m** past the apex.

What the extras actually reported is the *length of the measurement window*:

| apex used | bound | reported `trail_brake_depth_m` | true depth (distance order) |
|---:|---:|---:|---:|
| 1716.0 | 1775.0 | **59.0** | 0.17 |
| 1729.0 | 1775.0 | **46.0** | 0.20 |
| 1731.0 | 1775.0 | **44.0** | 0.43 |
| 1731.0 | 1775.0 | **44.0** (the reference) | 0.17 |
| 1738.0 | 1775.0 | **37.0** | 0.35 |

`reported == bound − apex` in every row. Nothing is flagged, and the value
(13–59 m) looks exactly like a plausible trail braking depth.

## Root cause

`lap_distance_m` does **not** start at 0 at the lap boundary: it starts at the
sim's current axis value and wraps to 0 part-way through the lap. In this
session 15 of the 17 eligible laps start at **4652–4654 m**; the axis wraps to 0
somewhere before the corners. The two laps that start at −1.5 / −2.3 m behave
correctly (see `artifacts/wrapped_laps.csv`).

`session_corner_extras._trail_depth()` walks rows in **file order**:

```python
for distance, pressure in zip(distances, brake):
    if distance <= apex_m or pressure is None:
        continue
    if distance > end_m:      # <-- row 0 of a wrapped lap is already past it
        break
    if pressure <= BRAKE_ON:
        return max(0.0, distance - apex_m)
return max(0.0, end_m - apex_m)   # "still on the brake at the bound"
```

Row 0 sits at 4652 m, which is beyond every corner's bound, so the loop breaks
immediately and the fallback fires: the corner is reported as braking for the
whole window. 115 of 129 `_trail_depth` calls in this session (89%) took that
path; the 14 that did not are the two non-wrapped laps and their corners.

The reference file is affected the same way (its first row is at 4652.43 m), so
both sides of every comparison are fabricated — and, because both fallbacks
return `bound − apex`, they can look *consistent* with each other.

## Impact

- `CornerExtras.trail_brake_depth_m` is a fabricated, plausibly-sized number for
  every corner of every wrapped lap.
- It is consumed by `session_priorities._clause_trail` → the driver is told to
  "hold the brake N m past the apex", and by `session_brief.py` (per-corner
  trail column) and the aggregated per-corner medians in
  `session_corner_extras.py:532`.
- It reaches the plan: the Repsol target for the next stint was derived from it.
- It is silent. No exception, no warning, and the existing tests use fixtures
  whose axis starts near 0 (`dev/scripts/test_session_corner_extras.py`
  asserts `tour.trail_brake_depth_m > 20`, which the fallback would happily
  satisfy).

## Repro

Artifacts in `artifacts/`: one CSV per eligible lap of the offending session
(`row, lap_distance_m, brake_norm, gear`, rows 1660–1800 m plus the lap's first
row), the reference lap, and `wrapped_laps.csv` with the summary table above.

```python
import csv
rows = list(csv.DictReader(open("artifacts/lap01_t4.csv")))
pts = [(float(r["lap_distance_m"]), float(r["brake_norm"])) for r in rows]
apex, bound, BRAKE_ON = 1716.0, 1775.0, 0.05

def current(pts):                      # session_corner_extras._trail_depth
    for d, b in pts:                   # pts[0] is the lap's first row: 4652.96 m
        if d <= apex: continue
        if d > bound: break            # fires on row 0
        if b <= BRAKE_ON: return max(0.0, d - apex)
    return max(0.0, bound - apex)

def correct(pts):                      # distance order, same rule
    for d, b in sorted(p for p in pts if apex < p[0] <= bound):
        if b <= BRAKE_ON: return d - apex
    return None

print(current(pts), correct(pts))      # 59.0  0.172
```

## Adjacent defect found while investigating (not filed separately)

The headline's `44 m` did not come from the trail fact at all — it came from
`_clause_exit` on **lap 15**, the only lap whose exit phase was classified
`exit_brake` (phase 1736 m vs reference 1780 m → `exit_distance_delta_m = 44`).
The other 13 exit detections sit at 1775–1825 m with deltas of +5, −1, −10, −23,
−24, −31, −34, −44, −45 (median **+5**). A single-lap phase label therefore
produced a session-wide instruction.

Separately, 6 of the 17 laps report `brake_peak = 0.0` at Repsol (laps 3, 5, 8,
14, 17, 18) although the brake trace is clearly non-zero through that window —
most likely the same family of row-order/detected-entry assumption, not
investigated.

## Fix (analysis side)

Root cause confirmed 2026-11: the wrapped axis is **not** a recorder defect.
The axis recorded is the sim's own `mLapDist` (the recorder also keeps it
faithfully as `raw_lap_distance_m`), the wrap at the start/finish line is a
documented property of exported laps (`docs/specs/MAP_TURN_NAMES.md`), every
committed reference lap in `product/data/reference-laps/` has it, and 15 of the
17 laps in the reported session have it. A recorder change could not retro-fix
any of that, so the analysis has to be order-independent.

`_trail_depth()` now:

1. Scans `(distance, brake)` pairs inside `(apex, bound]` **sorted by distance**
   instead of by row, so the row that happens to sit first cannot end the search.
2. Returns `None` when no release is found inside the window — a brake still on
   at the bound is unmeasurable, not `bound − apex`. `None` flows through
   `session_priorities._clause_trail`, `session_brief` and the medians, so
   nothing is coached about a depth we cannot see.

Regression coverage in `dev/scripts/test_session_corner_extras.py`:
`test_wrapped_distance_axis` (the synthetic lap rotated so row 0 sits past the
corner — reported 80 m before, 20 m after), `test_never_released_is_unmeasurable`
(including a row past the bound) and the real-session check on la Tour, which no
longer asserts the fabricated `> 20 m` but the true trace: the reference is off
the brake by the apex (0.01 m).

Measured on the local Barcelona practice `20260510T063243Z`: t4 lap 1 went from
51.0 m (window) to 6.8 m, lap 2 from 39.0 m to 0.73 m.

## Status

✅ Fixed in `session_corner_extras._trail_depth` — see "Fix (analysis side)".
