# Bug 29 — Greedy nearest-apex match lets a curated flat corner steal a neighbouring corner's braking event

**Status:** ✅ **Closed** — fixed in `776519f`, live-validated in `7ffa144`
(Fuji P3 quali refresh, 1:36.564 → 1:36.544) and confirmed by the user on
2026-11-07. Moved to `work/completed/bugs/`.

## Symptom

`update_reference_and_coaching_model.py --allow-unmatched` silently corrupts
curated **flat** corners when the flat corner sits within 150 m of a real
(braked) corner's apex: the flat corner absorbs the real corner's braking
event, and the real corner is then reported as "unmatched — keeps old
geometry". The refreshed model ends up with two corners on the same geometry
and a flat marker sitting on the neighbour's braking zone.

Observed twice on Fuji Speedway / Ginetta LMP3 (three times counting the
2026-11-07 dry run, which was aborted before writing):

| refresh | flat corner | real corner | wrong result |
|---|---|---|---|
| `927c727` (ref 1:37.414) | Netz @ 3310 m | Netz Hairpin @ 3408 m | Netz moved to the hairpin event |
| `125716c` (ref 1:36.564) | Netz @ 3310 m | Netz Hairpin @ 3404 m | Netz moved to 3291/3404/3439 |
| 2026-11-07 quali lap 2 (ref 1:36.544, **not applied**) | Netz @ 3310 m | Netz Hairpin @ 3404 m | would move Netz to 3289/3385/3446 (+136 m exit); Netz Hairpin unmatched |

The 2026-11-07 occurrence was caught in the dry run and nothing was written —
the 20 ms-faster lap was rejected as a model source for other reasons too (see
`work/active/track-outline/46-fuji-p3-quali-reference/handoff.md`).

In the two applied refreshes the model had to be corrected by hand after the
run, and the run's own audit did not flag anything:

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

## Fix — applied in `776519f`

`match_corners()` now ranks **every** legal (curated corner, candidate) pair by
apex distance and serves the closest pair first:

```python
ranked = sorted((abs(event.apex_m - corner["apex_s_m"]), corner_index, candidate_index) ...)
for distance, i, j in ranked:            # ascending: nothing closer follows
    if distance > MAX_APEX_DELTA_M: break
    if i in matches or claimed[j]: continue
    matches[i] = candidates[j]; claimed[j] = True
```

The hairpin's 19 m match now wins over Netz's 75 m match and Netz stays
unmatched. The `(distance, corner_index, candidate_index)` sort key keeps exact
ties deterministic (earlier corner first), and `--preserve-geometry` plus the
unknown-ID failure are unchanged.

Regression test added: `test_nearest_corner_claims_the_event_not_the_earlier_listed_one`
in `dev/scripts/test_update_coaching_model.py`, using the exact Fuji shape (flat
marker at 3310 m, real corner at 3404 m, event at 3385 m) and asserting the
marker is unmatched, keeps its geometry and keeps `target_throttle_pct`, while
the real corner takes the new geometry. It failed 4 assertions before the fix.

Re-running the old and new algorithms on the five reference laps already in the
repo found **eight** ownership differences, all of the same shape and all
corrected: Fuji `Netz`/`Netz Hairpin`, Interlagos `Ferradura 1`/`2`, Long Beach
`Turn 3`/`4` and `Turn 10`/`11`. Imola and Road Atlanta were unaffected. The
real Fuji dry run now aborts on `13th Corner, Netz` — the corners that truly
have no event — instead of `13th Corner, Netz Hairpin` with a corrupted Netz.

Heuristic note: a curated corner still claims an event within 150 m if no
closer corner wants it. That is deliberate (it is what refreshes compound and
light-braking corners); reviewed zones that must never match still need
`--preserve-geometry`.

## Live validation — 2026-11-07 (`7ffa144`)

The Fuji P3 refresh for the 1:36.544 quali lap was run **without**
`--preserve-geometry`, letting the fixed matcher decide ownership on its own:

```
Netz         3284/3310/3310 -> 3284/3310/3310   (KEPT, curated marker)
Netz Hairpin 3291/3404/3439 -> 3289/3385/3446   (its own event, 19 m away)
13th Corner  3100/3151/3161 -> 3100/3151/3161   (KEPT, curated marker)
```

The old matcher moved `Netz` to 3289/3404/3439 (+129 m of exit) on this same lap
and reported the hairpin unmatched. All 11 names, IDs, short names and apex
sides came through identical, the reference export passed its audit, and the
user confirmed the result in the car/map. The `--preserve-geometry netz
netz_hairpin` workaround is no longer needed.

## Files

- `dev/scripts/update_reference_and_coaching_model.py` — `match_corners()` (fixed)
- `dev/scripts/test_update_coaching_model.py` — regression case added
- `docs/HOW_TO_CREATE_A_COACHING_MODEL.md` — the `--allow-unmatched` caveat that
  described this failure mode was corrected
- Worked-around (not fixed) in `927c727` and `125716c`; fixed in `776519f`,
  live-validated in `7ffa144` (Fuji P3 quali refresh), user-confirmed 2026-11-07
