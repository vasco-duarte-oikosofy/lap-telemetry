# Handoff — Slice 37 (Monza Curva Grande / Ferrari 296 GT3)

## What was found

| Combo | Reference before | Reference now |
|---|---|---|
| Monza Curva Grande / Ginetta LMP3 (`dkr-engineering-4-elms25`) | 1:35.182 | **unchanged** — still the fastest Ginetta lap on disk |
| Monza Curva Grande / Ferrari 296 GT3 (`vista-af-corse-2026-54-wec`) | **none** | **1:39.398** |

The two newest Monza Curva Grande sessions are both Ferrari 296 GT3
(`Vista AF Corse 2026 #54:WEC`), and the combo had no reference lap and no
coaching model — only the Ginetta LMP3 pair existed. The F296 times are not
comparable with the Ginetta's (GT3 vs LMP3), so the F296 combo needed its own.

| Session | Fastest valid lap | Note |
|---|---|---|
| `session_20261031T153531Z_monza-curva-grande-circuit_lmu_practice.parquet` | 1:41.007 (lap 12) | |
| `session_20261031T152017Z_monza-curva-grande-circuit_lmu_practice.parquet` | **1:39.398 (lap 6)** | exported as the reference |
| `session_20261031T065746Z_…` (Ginetta) | 1:35.182 (lap 12) | already the reference |
| `session_20261031T080818Z_…` (Ginetta) | — | no complete lap |

## Files written

| File | What |
|---|---|
| `product/data/reference-laps/monza-curva-grande-circuit_vista-af-corse-2026-54-wec_time_01.39.398.parquet` | 4957 rows, segment-sliced lap 6 of the 15:20 session; `validate_reference_laps.py` OK (32 refs, 0 failures) |
| `product/data/track-coaching/monza-curva-grande-circuit_vista-af-corse-2026-54-wec.json` | 10 corners, **official names + IDs + apex sides + both flat markers preserved** from the curated Ginetta model |
| `product/data/track-coaching/monza-curva-grande-circuit_vista-af-corse-2026-54-wec.diagnostics.txt` | auto-detection log for the F296 lap |
| `work/active/track-outline/37-monza-curva-grande-f296/artifacts/seed_model_from_curated.py` | how the model was seeded (copies the curated content, points it at the new reference) |

## How the model was built (without losing curated content)

1. Seeded `…_vista-af-corse-2026-54-wec.json` from the curated
   `…_dkr-engineering-4-elms25.json` — names, IDs, `apex_side` +
   `apex_side_source: manual`, and the `target_throttle_pct: 100` markers on
   **Curva Grande** and **Curva del Serraglio**.
2. Ran the guarded updater from the new reference
   (`update_reference_and_coaching_model.py --ref … --allow-unmatched`). It
   re-checked all 10 curated corners against the F296 lap before writing.

Result: **5 corners refreshed** to F296 geometry, **5 kept** the LMP3 geometry
because a GT3 lap produces no separate braking event there:

| Corner | Apex before → after |
|---|---|
| Variante della Roggia 1 | 2109 → 2107 (−2 m) |
| Lesmo 1 | 2521 → 2505 (−16 m) |
| Lesmo 2 | 2833 → 2820 (−13 m) |
| Variante Ascari 1 | 3910 → 3913 (+3 m) |
| Curva Alboreto (Parabolica) | 5128 → 5138 (+10 m) |

Kept (unmatched, `--allow-unmatched`): Curva Grande *(flat)*, Variante della
Roggia 2, Curva del Serraglio *(flat)*, Variante Ascari 2, Variante Ascari 3.

## Verified

- Names / IDs / apex sides / flat markers **identical** to the curated model
  (asserted programmatically, see below).
- Coach resolution: every Ferrari 296 GT3 livery
  (`Vista AF Corse 2026 #54:WEC`, the `Corsa` misspelling, `2025 #21:LM`) resolves
  to the new pair; the Ginetta still resolves to its own.
- `generate_utterance --print-facts` on the 1:41.007 lap:
  `lap_time_delta_s 1.609` (exactly 101.007 − 99.398), corners resolve to real
  names (`Variante della Roggia 2`, `Lesmo 1`, …), no KeyError.
- Fast suite: 1005 passed; the 5 failures are the pre-existing Windows
  `ERR_UNSUPPORTED_ESM_URL_SCHEME` harness ones.

## Not done / next

- The 5 kept corners still carry LMP3 zone boundaries. If the F296 model ever
  gets a genuinely faster lap with separate braking events at the Ascari and
  Roggia complexes, re-run the updater and it will refresh them.
- No visual QA needed: the outline (`product/data/track-outlines/…`) was not
  touched, only the per-car reference + model.
