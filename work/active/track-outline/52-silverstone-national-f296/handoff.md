# Handoff — Slice 52: Silverstone National Circuit / Ferrari 296 GT3 (new car, existing track)

## Result

`(silverstone-national-circuit, ferrari-296-gt3)` now resolves in the live coach
for the first time. Reference lap and coaching model only — **no outline work**
(confirmed byte-identical, see "Untouched").

| Asset | File |
|---|---|
| Reference | `product/data/reference-laps/silverstone-national-circuit_vista-af-corse-2026-21-lm_time_00.54.295.parquet` |
| Model | `product/data/track-coaching/silverstone-national-circuit_vista-af-corse-2026-21-lm.json` |
| Diagnostics | `product/data/track-coaching/…_vista-af-corse-2026-21-lm.diagnostics.txt` |

Commits: `edc3930` (ref) → `9c19ee2` (model) → `0915a70` (tests) → this one (docs).

## The lap

| Session (2026-11-14) | Complete laps | Fastest |
|---|---|---|
| 06:52 quali | 10 | **0:54.295** (lap 8, 2703 rows) ← exported |
| 07:04 race | 31 | 0:54.696 (lap 20) |

Fastest in the whole scan was the quali lap, so the race is only the
cross-check. Both sessions carry `Vista AF Corse 2026 #21:LM`, which was
already catalogued as `ferrari-296-gt3` (no catalog work needed).

`artifacts/session-scan.txt` is the segment scan of both files — nothing is
selected by `lap_number` anywhere.

## The race recording was (still is) unfinalized

Sidecar says `in_progress: true`, `ended_utc: null`, no canonical parquet —
only `partN` shards and 12 `snapN` snapshots. The data itself is **complete**:
parts `0..99` run to session_time 2010.8 s / lap 33, then parts `100..105` are
frozen-time duplicates (car parked after the race ended).

- `artifacts/freeze_source.py` concatenated the closed parts below the highest
  one and collapsed 7619 exact-duplicate consecutive rows (107 463 → 99 844).
- Frozen copy: `var/tmp/silverstone-national-f296-quali-race/` (git-ignored),
  canonical session basename + sidecar so the exporter's track-slug parser and
  the validator's provenance scan both resolve it.
- SHA-256 of all 106 shards + the frozen file: `artifacts/source-manifest.json`.
- **If the recorder ever finalizes this race, re-run the guarded command** —
  the frozen file is a prefix of the closed shards, so the current reference is
  correct, but a faster lap could exist in the tail that was still open.

```bash
py dev/scripts/export_fastest_reference_laps.py --min-lap-time-s 30 \
  sessions/session_20261114T070413Z_silverstone-national-circuit_lmu_race.parquet \
  sessions/session_20261114T065241Z_silverstone-national-circuit_lmu_quali.parquet
```

## How the model was built (2 steps, both guarded)

1. `artifacts/seed_model_from_curated.py` — one-shot. Copies the curated P3
   model's corners verbatim (names, ids, apex sides, `apex_side_source`, both
   `target_throttle_pct: 100` markers) and points `reference_lap` at the new
   file. `lap_length_m` stays **2639.1** — the same simulator distance axis the
   P3 model and the baked outline use.
2. `update_reference_and_coaching_model.py --ref … --preserve-geometry maggots woodcote`

   Without `--preserve-geometry` it aborts (correctly) with:

   ```
   ABORTED - curated corners not reproduced on this lap: Maggots, Woodcote
   ```

   — a flat bend has no braking event, so on *every* lap those two are
   unmatched. Evidence: `artifacts/dry-run-no-preserve.txt` (abort) and
   `artifacts/signal-review.txt` (throttle 1.00 / brake 0.00 across both zones,
   and the full profile around all six).

### Geometry

| Corner | P3 geometry (seed) | F296 geometry (now) | Why |
|---|---|---|---|
| Copse | 242 / 359 / 435 | **206 / 368 / 372** | braked right; this lap's brake onset is ~211 and the speed minimum 368. Exit 372 is the throttle onset — see the deferred note |
| Maggots | 790 / 828 / 833 | **preserved** | flat left, `target_throttle_pct: 100` |
| Becketts | 834 / 1068 / 1089 | **884 / 1046 / 1086** | braked right, apex −22 m |
| Brooklands | 1740 / 1921 / 1960 | **1746 / 1925 / 1957** | braked left, apex +4 m |
| Luffield | 2003 / 2102 / 2153 | **2003 / 2092 / 2103** | braked right, apex −10 m |
| Woodcote | 2360 / 2469 / 2580 | **preserved** | flat right, `target_throttle_pct: 100` |

No zone overlaps: Maggots ends 833, Becketts starts 884 (51 m of clear track).
Zone ordering, sides and ids identical to the P3 model
(`artifacts/curation-check.txt`: names/ids/sides/flat markers all `PRESERVED`).

## Deferred: Copse's exit is a throttle-onset boundary

Copse now has `s_end_m 372`, i.e. 4 m past its apex. That is the detector's
read of "full throttle resumes", and exit gaps of 0–14 m are the **corpus
norm** (most models in `product/data/track-coaching/` look like this), so it is
consistent rather than broken. But the P3 model for this same corner carries a
hand-reviewed `435`, chosen because the P3's exit throttle modulates over a
363–476 m spread (slice 51). If the coach's Copse exit-phase note feels noisy
for the 296, the fix is to re-curate Copse's exit by hand from a multi-lap
spread — not to re-run the updater.

## Verified

- `artifacts/reference-validation.txt`: **38 references, 0 failures**; the new
  reference traces to the 2026-11-14 quali session.
- `artifacts/lap20-facts.json`: race lap 20 (0:54.696) vs the new reference
  reports `lap_time_delta_s 0.401` exactly (0.401 = 54.696 − 54.295); corner
  names resolve (`Becketts`, `Luffield`, `Woodcote`), no unreferenced corner ids.
- `bash scripts/test-summary.sh --feature track-outline`:
  **1332 assertions / 31 scripts** (36 registered, 5 Playwright skipped).
- Full `bash scripts/test-summary.sh --pw`: **2795 assertions / 97 scripts — ALL PASS**.
- `npm run build` succeeded; `dist/compare.html` rebuilt with **no content
  change** (this slice touches no web asset).
- `artifacts/scope-audit.txt`: 6 files changed (ref, model, diagnostics, 2 test
  files, package.json). 37 other references, 38 other coaching models, 27
  outlines untouched.

## Untouched on purpose

- `product/data/track-outlines/silverstone-national-circuit.json` — the outline
  baker still selects the P3 model (alphabetically first with named corners), so
  the outline contract holds **without** a re-bake. The new test pins that its
  anchors still match the P3 model, so a future accidental re-bake fails loudly.
- TinyPedal `Silverstone National Circuit.turns.json` (derived from that outline).
- Silverstone GP-ELMS / International assets, every other track.
- `coach-race.log` at the repository root (live coach runtime artifact).

## Next steps for the driver

1. **Restart the coach** so the new reference and model are picked up.
2. A GT3 lap at Silverstone National has no prior baseline — 0:54.295 is the
   first, not a settled limit. Four race laps were within 0.5 s of it. Any later
   quali/race is the entire refresh procedure:

```bash
py dev/scripts/update_reference_and_coaching_model.py \
  --session <session parquet> --track-id silverstone-national-circuit \
  --preserve-geometry maggots woodcote --min-lap-time-s 30
```
