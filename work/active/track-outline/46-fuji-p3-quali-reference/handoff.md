# Handoff — Slice 46 (Fuji P3 quali + race check)

## Bottom line

**Nothing was changed.** The fast quali lap (1:36.544) is 20 ms quicker than the
1:36.564 reference, and it is a worse model source than the lap already in use.
The reference, model, diagnostics, outlines, static modules and bundle are all
byte-identical to before this slice (`artifacts/before-state.json`).

## The numbers

| Lap | Session | Time | Events detected |
|---|---|---|---|
| **quali lap 2** | 14:18 | **1:36.544** | 9 |
| quali lap 3 | 14:18 | 1:36.682 | 9 |
| race lap 10 | 14:27 | 1:36.770 | 9 |
| race lap 12 | 14:27 | 1:36.779 | 9 |
| current reference | — | 1:36.564 | 9 |

Only quali lap 2 beats the reference. Everything else in today's Fuji sessions
(09:41/09:46 practice, 09:48 quali, 09:57 race, 14:04/14:15/14:16 practice) is
1:36.787 or slower, and no other car ran this layout.

## Why not update — four independent reasons

1. **No new information.** 9 events on both laps; identical structure.
2. **Two corners are manual markers.** `13th Corner` (3100/3151/3161) and `Netz`
   (3284/3310/3310) have no braking event within 5 m on the *current* reference
   either — they were curated by hand and cannot be refreshed by any lap.
3. **Bug 29 would corrupt Netz.** Greedy model-order matching lets `Netz`
   (3310) claim the Netz Hairpin event (3385) 75 m away and +136 m of exit
   movement; `netz_hairpin` then reports unmatched. Third occurrence of the same
   bug on the same corner (see `work/active/bugs/29-…/bug.md`).
4. **The rest is noise.** Clean-lap spread on these two sessions: `100R` event
   apex 1626–1761 m (135 m), `Panasonic` 3650–3695 m. A +44 m move for 100R on
   this lap is sampling noise, not geometry.

## Safe command if the 20 ms is ever wanted

```bash
python dev/scripts/update_reference_and_coaching_model.py \
  --session sessions/session_20261107T141839Z_fuji-speedway_lmu_quali.parquet \
  --track-id fuji-speedway \
  --allow-unmatched --preserve-geometry netz netz_hairpin 13th_corner
```

`--preserve-geometry` is what keeps bug 29 out of the write. Without it, the
`--max-geometry-delta-m 40` guard aborts the run (it did here).

## Evidence

| File | What |
|---|---|
| `artifacts/session-laps.txt` | lap tables for both sessions |
| `artifacts/update-dry-run.txt` | the guard aborting on `13th Corner`, `Netz Hairpin` |
| `artifacts/decision-evidence.txt` | events per lap, matcher output, manual-marker proof, noise spans |
| `artifacts/decision_evidence.py` | read-only script that reproduces the file above |
| `artifacts/before-state.json` | hashes proving no product file changed |

## Not done / next

- **Bug 29 is still open.** Fix direction is already written in `bug.md`
  (claim candidates globally nearest-first instead of model-order). Once fixed,
  the `--preserve-geometry` workaround for `netz`/`netz_hairpin` is no longer
  needed — but this reference still would not be worth replacing for 20 ms.
- Fuji P3 reference has not moved since `125716c`; the model's 11 corners come
  from that lap plus two manual markers.
- If a lap appears that is **≥ 0.2 s** faster, the same dry run will show
  whether it separates Netz from Netz Hairpin; only then is a refresh useful.
