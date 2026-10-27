# Bug 29 — Greedy nearest-apex match lets a curated flat corner steal a neighbouring corner's braking event

## Symptom

`update_reference_and_coaching_model.py --allow-unmatched` silently corrupts
curated **flat** corners when the flat corner sits within 150 m of a real
(braked) corner's apex: the flat corner absorbs the real corner's braking
event, and the real corner is then reported as "unmatched — keeps old
geometry". The refreshed model ends up with two corners on the same geometry
and a flat marker sitting on the neighbour's braking zone.

Observed twice on Fuji Speedway / Ginetta LMP3:

| refresh | flat corner | real corner | wrong result |
|---|---|---|---|
| `927c727` (ref 1:37.414) | Netz @ 3310 m | Netz Hairpin @ 3408 m | Netz moved to the hairpin event |
| `125716c` (ref 1:36.564) | Netz @ 3310 m | Netz Hairpin @ 3404 m | Netz moved to 3291/3404/3439 |

Both times the model had to be corrected by hand after the run, and the run's
own audit did not flag anything:

```
Corner check: model has 11, lap yields 9 (9 matched)
  WARNING: 13th Corner keeps old geometry (--allow-unmatched)
  WARNING: Netz Hairpin keeps old geometry (--allow-unmatched)
  ...
  Netz        3291.0   3404.0   3439.0  (was 3284.0 / 3310.0 / 3310.0)
  Netz Hairpin 3266.0   3408.0   3437.0  (was 3266.0 / 3408.0 / 3437.0)
```

## Root cause

`match_corners()` in `dev/scripts/update_reference_and_coaching_model.py`
walks the **existing model in corner order** and lets each curated corner claim
its nearest *unclaimed* candidate within `MAX_APEX_DELTA_M` (150 m):

```python
for old_c in existing_corners:
    idx = nearest(float(old_c["apex_s_m"]))
    if idx is not None:
        claimed[idx] = True
        pairs.append((old_c, candidates[idx]))
```

Order, not distance, decides ownership. Fuji's model lists `netz` (3310 m)
before `netz_hairpin` (3408 m), so `netz` is served first and takes the
hairpin's event (94 m away — legal under the 150 m tolerance); when
`netz_hairpin` is served, its own event is already claimed and its nearest
remaining candidate is 257 m away → recorded as unmatched. The flat corner has
*no* braking event of its own, so a 94 m match is exactly the signal that it
should not match at all.

`--max-geometry-delta-m` is the only thing that catches this today, and only if
the operator happens to pass a threshold below the flat corner's displacement
(here 129 m of exit movement).

## Reproduction

Read-only, no writes (needs the Fuji P3 session used by `125716c`):

```bash
export PATH=".venv/Scripts:$PATH" PYTHONPATH=product/python
python3 - <<'PY'
import json, sys, tempfile
from pathlib import Path
import pyarrow.parquet as pq
sys.path.insert(0, "dev/scripts")
from export_fastest_reference_laps import find_complete_laps
from update_reference_and_coaching_model import detect_corners, match_corners

sess = Path("sessions/session_20261025T070440Z_fuji-speedway_lmu_race.parquet")
t = pq.read_table(sess)
lap = min(find_complete_laps(t), key=lambda c: c[1])          # 1:36.564
tmp = Path(tempfile.gettempdir()) / "bug29.parquet"
pq.write_table(t.slice(lap[2], lap[3] - lap[2]), tmp)
cands, _ = detect_corners(tmp)
model = json.loads(Path(
    "product/data/track-coaching/fuji-speedway_dkr-engineering-4-elms25.json").read_text())
for old_c, m in match_corners(model["corners"], cands)[0]:
    if old_c["id"] in ("netz", "netz_hairpin"):
        print(old_c["id"], old_c["apex_s_m"], "->",
              "UNMATCHED" if m is None else f"{m.s_start_m}/{m.apex_m}/{m.s_end_m}")
PY
```

Current (buggy) output: `netz` claims `3291/3404/3439`, `netz_hairpin` is
UNMATCHED. Expected: `netz` UNMATCHED (flat corner keeps its geometry) and
`netz_hairpin` claims `3291/3404/3439`.

## Fix direction

Claim candidates in ascending match distance (globally nearest pair first)
instead of in model order: build all (old corner, candidate, distance) pairs,
sort by distance, then assign greedily. The hairpin's 4 m match then wins over
Netz's 94 m match, and Netz stays unmatched. Add a regression test to
`dev/scripts/test_update_coaching_model.py` with the exact Fuji-shaped fixture
(flat corner 94 m from a real corner's apex, listed before it) asserting the
flat corner is unmatched and keeps its `target_throttle_pct`.

Consider also refusing a match when the candidate has no braking event at all
while the curated corner is marked flat — but the ordering fix alone resolves
the observed failure and needs no new heuristics.

## Files

- `dev/scripts/update_reference_and_coaching_model.py` — `match_corners()`
- `dev/scripts/test_update_coaching_model.py` — needs the regression case
- Worked-around (not fixed) in `927c727` and `125716c`
