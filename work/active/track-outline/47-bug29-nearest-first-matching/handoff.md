# Handoff — Slice 47 (bug 29 fixed: nearest-first matching)

## State on disk

| File | Change |
|---|---|
| `dev/scripts/update_reference_and_coaching_model.py` | `match_corners()` rewritten: rank all (corner, event) pairs by apex distance, claim globally nearest-first; ties keep the earlier corner |
| `dev/scripts/test_update_coaching_model.py` | +2 tests (`test_nearest_corner_claims_the_event_not_the_earlier_listed_one`, `test_matching_is_deterministic_and_respects_the_distance_cap`) |
| `docs/HOW_TO_CREATE_A_COACHING_MODEL.md` | `--allow-unmatched` caveat corrected (a listed-earlier corner can no longer steal) |
| `work/active/bugs/29-flat-corner-steals-neighbour-braking-event/bug.md` | status → ✅ Fixed, third occurrence recorded |
| `work/active/track-outline/47-bug29-nearest-first-matching/` | prompt, this handoff, learnings, artifacts |

**No product data changed**: no reference lap, coaching model, outline, static
module or bundle was touched. The fix is behaviour-only, and the committed
models were already hand-corrected for the historical damage.

## What changes for the next refresh

- A curated corner only claims an event when it is the **closest** corner to it.
  So flat/manual markers (Fuji `Netz`, Long Beach `Turn 3`/`Turn 10`, Interlagos
  `Ferradura 1`) now come back as **unmatched** instead of stealing — which is
  what `--allow-unmatched` is for, and their `target_throttle_pct` survives.
- `--preserve-geometry` is still the right tool when a reviewed zone must not
  claim an event *at all* (it now only matters for corners that really are the
  nearest to a neighbour's event, e.g. Long Beach `t7`).
- The Fuji command documented in slice 46 now yields:
  `ABORTED - curated corners not reproduced: 13th Corner, Netz` — the honest
  answer. With `--allow-unmatched` it would refresh the other 9 and keep those
  two; the `--preserve-geometry netz netz_hairpin 13th_corner` workaround is no
  longer required (harmless if left on the command line).

## Evidence

| File | What |
|---|---|
| `artifacts/real-data-dry-run.txt` | Fuji 1:36.544 dry run after the fix (aborts with the *correct* unmatched pair) |
| `artifacts/matching-before-after.txt` | old vs new ownership on 5 real reference laps: 8 differences, all corrections |
| `artifacts/matching_before_after.py` | read-only script reproducing that table (contains the legacy algorithm verbatim) |
| `artifacts/summary.txt` | unit-test result + the corrected dry-run output |

## Verified

- `node dev/scripts/test_update_coaching_model.js` → 31/31 (was 27/31 before the fix).
- `bash scripts/test-summary.sh --feature track-outline` → 960 assertions pass.
- Full `--pw` suite → 2037 assertions over 80 scripts pass.
- `git status` after the runs: only the source/test/doc files above.

## Not done / next

- **Bug 29 folder is still in `work/active/bugs/`** — AGENTS.md says it moves to
  `work/completed/bugs/` only after you confirm a live test. The natural live
  test: run a refresh on a track where a marker corner sits next to a real one
  (Fuji with `--allow-unmatched`) and check the marker keeps its geometry.
- No data re-derivation was done, and none is needed: every committed model
  already has distinct apexes for these pairs.
- `refresh_corners()` and the guards are unchanged; nothing else in the updater
  was touched.
