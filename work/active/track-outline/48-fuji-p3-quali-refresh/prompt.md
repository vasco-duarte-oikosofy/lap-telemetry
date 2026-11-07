# Slice 48 — Fuji / Ginetta P3: live validation of the bug 29 fix

Status: ✅ Complete — reference and model refreshed; bug 29 behaved correctly on real data and the user accepted the result (bug closed 2026-11-07)
Trigger: *"LETs do the fuji/p3 quali lap update to validate the fix for bug 29"*

## What ran

```bash
python dev/scripts/update_reference_and_coaching_model.py \
  --session sessions/session_20261107T141839Z_fuji-speedway_lmu_quali.parquet \
  --track-id fuji-speedway \
  --allow-unmatched --max-geometry-delta-m 50
```

No `--preserve-geometry`: the point was to let the fixed matcher decide
ownership on its own.

- Fastest lap: **lap 2, 1:36.544** → new reference (4760 rows); the 1:36.564
  file was superseded and removed; `AUDIT: 1 reference lap changed`. OK.
- 9 of 11 corners refreshed; `13th Corner` and **`Netz`** unmatched, keeping
  their curated geometry.

## The validation (bug 29)

| Corner | before | after | verdict |
|---|---|---|---|
| **Netz** | 3284 / **3310** / 3310 | 3284 / **3310** / 3310 | **KEPT** — the old matcher moved this to 3289/3404/3439 |
| **Netz Hairpin** | 3291 / 3404 / 3439 | 3289 / **3385** / 3446 | refreshed by its own event (19 m away) |
| 13th Corner | 3100 / 3151 / 3161 | 3100 / 3151 / 3161 | kept (no event of its own) |

Before the fix this same lap produced `13th Corner, Netz Hairpin` unmatched and a
Netz sitting on the hairpin's event. Now the warning names the corners that
genuinely have no event, and the marker keeps its geometry. This is the live
confirmation bug 29 was fixed for.

## Other geometry moves (expected)

| Corner | apex before → after |
|---|---|
| First Corner | 766 → 771 |
| Coca-Cola | 1314 → 1326 |
| 100R | 1699 → **1743** (the noise flagged in slice 46) |
| Hairpin | 2013 → 2005 |
| Dunlop Bypass | 2846 → 2842 |
| Turn 11 | 2914 → 2918 |
| Turn 12 | 3132 → 3116 |
| Panasonic | 3672 → 3663 |

`--max-geometry-delta-m 50` was used deliberately: it admits 100R's expected
+45 m but would still have aborted a bug-29 style steal (+136 m).

## Follow-on work done automatically

- Outline `turns` re-baked from the new model + new reference (repo contract:
  `test_outline_turns.js` pins Fuji's anchors to the model) — 9 anchors moved,
  `13th Corner` (3151) and `Netz` (3310) unchanged.
- `Fuji Speedway.turns.json` re-exported to TinyPedal (`--check` clean), so the
  map labels follow the new apexes (largest shift: 100R 0.3743 → 0.3840).
- Static module + `dist/compare.html` rebuilt.

## Verified

- Curation: every name, id, short name, apex side identical to
  `artifacts/model-before.json` (`artifacts/curation-and-fix-check.txt`).
- `validate_reference_laps.py`: 35 refs, 0 failures. Note: its provenance line
  names the 2026-10-25 race because that session has a 1:36.564 lap within the
  tolerance; the exported file is byte-identical (row-for-row) to today's quali
  lap 2 (4760 rows) — see the handoff.
- `--print-facts` with the **old** reference lap as the current lap: exactly
  `lap_time_delta_s 0.02`, corner names resolve (`First`, `Hairpin`,
  `Netz Hairpin`, `Twelve`, `Panasonic`).
- Feature suite 960 assertions; full `--pw` suite 2037 assertions / 80 scripts.
- Scope: the reference (1 add, 1 delete), the model + its diagnostics, the Fuji
  base outline, its static module, the bundle, and one TinyPedal label file.
