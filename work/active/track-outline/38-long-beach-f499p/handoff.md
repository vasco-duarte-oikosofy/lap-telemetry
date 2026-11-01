# Handoff — Slice 38: Long Beach / Ferrari 499P

## Delivered assets

- Reference: `product/data/reference-laps/grand-prix-of-long-beach_ferrari-af-corse-2026-50-lm_time_01.15.889.parquet`.
- Model: `product/data/track-coaching/grand-prix-of-long-beach_ferrari-af-corse-2026-50-lm.json`.
- Outline: `product/data/track-outlines/grand-prix-of-long-beach.json`.
- Generated module: `product/web/js/staticGrandPrixOfLongBeachOutlineData.js`.
  Export: `GRAND_PRIX_OF_LONG_BEACH_STATIC_OUTLINE`.
- Manifest resolves both the exact LMU name Grand Prix of Long Beach and the
  recording slug. `product/dist/compare.html` rebuilt with the new outline.
- Vehicle catalog already maps Ferrari AF Corse 2026 #50:LM to ferrari-499p;
  no catalog changes were necessary. Both coach resolvers select this combo.

## Reference provenance

Source: `sessions/session_20261101T114510Z_grand-prix-of-long-beach_lmu_practice.parquet`.
The guarded exporter selects **lap 10 / 75.888671875 s / 3782 rows**, all valid.
Lap 4's apparently faster 75.735 s is abandoned: it contains -203.8 m garage
frames and only reaches 1217.7 m of the 3185.3 m lap. Never use it as a reference.

Export audit confirms exactly one reference added, none superseded and no
other reference changed. Whole-folder validator passes: 33 refs, zero failures.
Logs are in `artifacts/reference-export.txt` and `reference-validation.txt`.

## Official numbering and preserved geometry

Official organiser map: https://www.gplb.com/circuit-map (the public page now
serves a 2027 event edition). Stable numbered Turn 1–Turn 11 names are retained;
no invented or year-dependent sponsor names. Official route and left/right
sides were cross-checked against simulator positions and steering, calibrated at
known left T1 and right T8/T11. Details: `artifacts/geometry-review.md`.

The detector found only eight braking events:

- **Flat T3:** 940 / 950 / 990 m, left, target_throttle_pct 100.
- **Flat T7:** 1680 / 1725 / 1760 m, left, target_throttle_pct 100.
- Both are full real zones, confirmed full throttle/no braking, not zero-width
  markers or adjacent braking apices. Their full position shape remains in the
  500-point outline and all 11 map anchors are present.
- Left T10 (2620 / 2690 / 2760 m) and right hairpin T11
  (2761 / 2821 / 2834 m) are split rather than one merged detector event.
- Spoken aliases are 1…9, Ten, Eleven. Map displays T1…T11, not speech aliases.
- Outline boundaries are a **synthetic +/-5 m shell** around the reference
  racing line, not measured street walls or authoritative track limits.

## Guarded reproduction

`dev/scripts/create_long_beach_f499p_assets.py --detected <raw-generator.json>`
creates this combo only. Generate the raw JSON to `var/tmp/`, never regenerate a
curated product model directly. The helper verifies expected eight-event input,
adds reviewed geometry, bakes anchors and refuses to overwrite different
existing curated assets. Re-running unchanged is a no-op.

```bash
export PATH="$PWD/.venv/Scripts:$PATH" PYTHONPATH="$PWD/product/python" PYTHONUTF8=1
python dev/scripts/generate_track_coaching_model_from_reference.py \
  --reference-lap product/data/reference-laps/grand-prix-of-long-beach_ferrari-af-corse-2026-50-lm_time_01.15.889.parquet \
  --track-id grand-prix-of-long-beach --layout-id lmu-default \
  --car-id ferrari-af-corse-2026-50-lm --out var/tmp/long-beach-detected.json
python dev/scripts/create_long_beach_f499p_assets.py --detected var/tmp/long-beach-detected.json
```

**Future refresh warning:** bug 29's generic nearest-brake matcher can let flat
T3 steal T4's event (only 113 m away). Do not blindly refresh these flat corners
from braking events; preserve these reviewed zones and inspect any updater
preview/geometry guard. This slice does not change that shared matcher. The
new regression pins both flat zones and rejects curated asset overwrites.

## Verification

- Red first: missing assets and missing runtime registration.
- Feature: `bash scripts/test-summary.sh --feature long-beach-f499p --pw`
  passes: **592 assertions, 14 scripts**.
- Full: **1730 assertions, 71 scripts pass**, using the temporary Windows ESM
  URL adapter documented in coach slice 13's handoff. It only adapts Windows
  absolute import specifiers; stock bug-20 test imports remain unfixed.
- Reference validator: 33 refs, zero failures. Spoken-name corpus --check clean.
- Build succeeds; diff whitespace checks clean.
- Extracted lap 11 segment-aware and ran --print-facts: lap delta +0.153 s;
  facts resolve to the new official turn IDs. See `artifacts/lap11-facts.json`.
- Browser test opens the built standalone bundle via file:// and replays the
  committed practice reference with the actual recording filename: exact track
  resolves, 500-point centerline/boundaries render, static
  boundary pixels visible. `artifacts/outline.png` is evidence, not a pixel golden.

## Remaining QA

`visual_qa.status` stays pending for user live/by-eye approval. Automated render
and screenshot inspection pass, but real street-wall widths are not measured.
No feature flag was added. No other track/model/reference was modified.
