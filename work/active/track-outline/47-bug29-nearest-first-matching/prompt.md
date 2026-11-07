# Slice 47 — Fix bug 29: nearest-first corner matching

Status: ✅ Fixed (`776519f`) and live-validated (`7ffa144`, Fuji P3 1:36.544 refresh); user-confirmed 2026-11-07, bug folder moved to `work/completed/bugs/`
Trigger: *"let's fix bug 29 now"* — the greedy, model-order matcher in
`update_reference_and_coaching_model.py` that let a curated corner absorb its
neighbour's braking event.

## The bug in one line

Corners were served **in model order**, each claiming its nearest *unclaimed*
event within 150 m. So Fuji's `Netz` (3310 m, listed before `Netz Hairpin`)
took the hairpin's event at 3404 m — 94 m away — and the hairpin (right on the
event) was reported unmatched. Same shape at Interlagos (`Ferradura 1/2`) and
Long Beach (`Turn 3/4`, `Turn 10/11`).

## The fix

Every legal (corner, candidate) pair is ranked by apex distance and the closest
pair is served first, so ownership is decided by distance and not by list
position:

```python
ranked = sorted((abs(apex - corner.apex_s_m), corner_index, candidate_index) ...)
for distance, i, j in ranked:      # ascending: nothing closer follows
    if distance > MAX_APEX_DELTA_M: break
    if i in matches or claimed[j]: continue
    matches[i] = candidates[j]; claimed[j] = True
```

Ties resolve to the earlier corner (the `(distance, i, j)` sort key), so
existing behaviour is preserved wherever distances are equal.
`--preserve-geometry` and the unknown-ID failure are unchanged.

## Evidence

- **Test-first**: new `test_nearest_corner_claims_the_event_not_the_earlier_listed_one`
  (the Fuji-shaped fixture from bug 29) plus a determinism/distance-cap test.
  Before the fix: 27/31 assertions, 4 failures. After: 31/31.
- **Real data** (`artifacts/matching-before-after.txt`), old vs new on the
  five reference laps already in the repo — 8 ownership differences, all
  corrections:

| Track | was | now |
|---|---|---|
| Fuji | Netz takes 3404-19m event | NetzHairpin takes it, Netz unmatched |
| Interlagos | Ferradura 1 takes 2151 | Ferradura 2 takes it |
| Long Beach | Turn 3 takes 1045, Turn 10 takes 2828 | Turn 4 / Turn 11 take them |
| Imola, Road Atlanta | — | no difference |

- **The real Fuji dry run changed shape**: before the fix it reported
  `13th Corner, Netz Hairpin` unmatched (having already corrupted Netz); now it
  reports `13th Corner, Netz` — the two corners that genuinely have no event of
  their own — and Netz keeps its curated geometry.
- No data repair needed: the committed Interlagos, Long Beach and Fuji models
  were already hand-corrected after the historical corruptions (Ferradura 1
  2089 vs 2 2152; T3 950 vs T4 1045; Netz 3310 vs Netz Hairpin 3404).

## Boundaries

- `match_corners()` only; `refresh_corners()`, the guards, the export path and
  every curated data file are untouched.
- `docs/HOW_TO_CREATE_A_COACHING_MODEL.md`: the `--allow-unmatched` warning that
  a flat corner can steal a neighbour's event was made true-by-fix.
