# Handoff — Slice 43 (Imola / Ferrari 296 GT3)

## What was found

| Combo | Reference before | Reference now |
|---|---|---|
| Imola / Ginetta LMP3 (`dkr-engineering-4-elms25`) | 1:40.607 | **unchanged** |
| Imola / Ferrari 499P (`ferrari-af-corse-2026-50-lm`) | 1:33.546 | **unchanged** |
| Imola / Ferrari 296 GT3 (`vista-af-corse-2026-21-lm`) | **none** | **1:46.173** |

Today's session `sessions/session_20261107T075003Z_autodromo-enzo-e-dino-ferrari_lmu_practice.parquet`
(8 laps, practice, `Vista AF Corse 2026 #21:LM` → canonical `ferrari-296-gt3`):

| Lap | Time | Note |
|---|---|---|
| 1 | 1:50.608 | out lap |
| 2 | 1:48.429 | |
| 3 | 1:47.760 | |
| 4 | 1:46.552 | used for `--print-facts` |
| **5** | **1:46.173** | **exported reference** |
| 6–7 | 0:11.609 / 0:03.015 | incomplete |

## Files written

| File | What |
|---|---|
| `product/data/reference-laps/autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm_time_01.46.173.parquet` | 5292 rows, segment-sliced lap 5; `validate_reference_laps.py` OK (35 refs, 0 failures) |
| `product/data/track-coaching/autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm.json` | 11 corners; official names/IDs/apex sides/short names copied from the curated Ginetta model |
| `product/data/track-coaching/autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm.diagnostics.txt` | auto-detection log for the F296 lap (8 accepted events) |
| `work/active/track-outline/43-imola-f296/artifacts/seed_model_from_curated.py` | how the model was seeded (copies curation, points it at the new reference) |

Nothing else changed: no tracked file was modified, `product/data/track-outlines/autodromo-enzo-e-dino-ferrari.json`
is untouched, `dist/compare.html` rebuilt to an identical file.

## How the model was built

1. Exported the reference through `export_fastest_reference_laps.py`
   (`AUDIT: 1 reference lap changed`, added only).
2. Seeded `…_vista-af-corse-2026-21-lm.json` from
   `…_dkr-engineering-4-elms25.json` (the curated model the outline baker
   selects; it also has the Rivazza short names the 499P model lost).
3. Ran `update_reference_and_coaching_model.py --ref <new ref> --allow-unmatched`.
   The dry run without `--allow-unmatched` aborts on exactly the three compound
   second halves — that is the guard working, not a bad lap.

Result: **8 corners refreshed**, **3 kept** (old geometry) because a GT3 lap
brakes once per complex:

| Corner | Entry/Apex/Exit before → after |
|---|---|
| Tamburello | 524/704/710 → 513/699/710 |
| Variante Villeneuve 1 | 1225/1419/1441 → 1223/1413/1427 |
| Tosa | 1595/1696/1741 → 1604/1707/1747 |
| Piratella | 2194/2323/2332 → 2203/2333/2361 |
| Acque Minerali 1 | 2659/2841/2867 → 2652/2849/2853 |
| Variante Alta 1 | 3198/3385/3398 → 3251/3383/3393 |
| Rivazza 1 | 3981/4145/4156 → 3990/4119/4144 |
| Rivazza 2 | 4203/4256/4279 → 4196/4249/4291 |

Kept (unmatched, `--allow-unmatched`): **Variante Villeneuve 2**, **Acque
Minerali 2**, **Variante Alta 2**.

## About "keep the flat turns"

Imola's curated models carry **no** `target_throttle_pct` markers — neither the
Ginetta nor the 499P model ever had one, and `git log` on the Ginetta model
confirms it. None of the 11 corners is a flat-only bend: every one either brakes
or is the second half of a braking complex. The constraint therefore resolved
to: **keep every curated turn**, which is what `--allow-unmatched` + the seeded
curation do. If a flat marker is ever added at Imola, the updater already
preserves it (see `refresh_corners` and `test_update_coaching_model.py`).

## Outline

`product/data/track-outlines/autodromo-enzo-e-dino-ferrari.json` already exists
(slice 08, median trajectory, 11 official turns) and needs no change: outlines
are per-layout, and the baker still selects the Ginetta model (equal curated
names, tie broken by filename). `bake_outline_turns.py --check` prints `STALE`
only because a raw bake would write `Rivazza 1`/`Rivazza 2` short names, which
`BAKED_SHORT_NAMES` in `test_outline_turns.js` deliberately pins to numbers.
Evidence: `artifacts/outline-check.txt`.

## Verified

- **Curation byte-identical** to the source model (names, IDs, short names,
  apex sides, flat markers) — `artifacts/curation-check.txt`, exit 0.
- Resolution by canonical car: every 296 GT3 livery (`2026 #21:LM`,
  `2025 #21:LM`, `AF Corse 2025 #51:ELMS`, `Richard Mille AF Corse 2026 #50:ELMS`)
  → the new pair; `Ferrari AF Corse 2026 #50:LM` (499P) and
  `DKR Engineering #4:ELMS25` → their own. `artifacts/resolution-check.txt`.
- `--print-facts` on lap 4 (1:46.552): `lap_time_delta_s 0.379` exactly, corners
  resolve to official names (`Tamburello`, `Villeneuve 2`, `Tosa`, `Rivazza 2`),
  no `KeyError` — `artifacts/print-facts-lap4.txt`.
- Updater re-run is a no-op (`artifacts/update-idempotency.txt`).
- Feature suite `--feature track-outline`: 950 assertions / 25 scripts pass.
- Full suite `--pw`: 2027 assertions / 80 scripts pass.
- `npm run build`: `dist/compare.html` byte-identical (no bundle change).

## Not done / next

- The three preserved corners still carry Ginetta zone boundaries. If the F296
  ever produces a lap that brakes separately at Villeneuve/Acque/Alta, re-run the
  updater and they will refresh.
- 1:46.173 is a practice lap with only 8 laps; a faster F296 lap is likely.
  Re-running the updater with the new session is the whole procedure.
- Imola has no TinyPedal turn-label export yet (`export_turn_labels_for_tinypedal.py`
  needs the sibling TinyPedal map); slice 33 (Imola ELMS alias) is still open.
