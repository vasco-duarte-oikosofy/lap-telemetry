# Handoff — Slice 55: F296 / Silverstone National qualifying refresh

## Result

✅ Complete. Latest qualifying lap 10 replaces **0:54.295 → 0:54.106**
(0.189 s faster). Implementation commit: **`d0a5a8e`** (also in the mission PLAN).

- Source: `sessions/session_20261115T095239Z_silverstone-national-circuit_lmu_quali.parquet`
  (finalised, 2026-11-15 09:52 UTC, Vista AF Corse 2026 #21:LM).
- New reference:
  `product/data/reference-laps/silverstone-national-circuit_vista-af-corse-2026-21-lm_time_00.54.106.parquet`.
- Model/diagnostics:
  `product/data/track-coaching/silverstone-national-circuit_vista-af-corse-2026-21-lm.{json,diagnostics.txt}`.
- Regression: `dev/scripts/test_silverstone_national_f296.py`, through its
  existing Node wrapper and `track-outline` feature registration.

The selected contiguous segment is source rows **30117:32811** (2,694 rows),
all valid. Telemetry-clock duration is 54.106018 s; export metadata/filename
round to 54.106. Wall-clock span is 54.0 s, consistent with the 5 Hz clock.
Eight complete laps passed the exporter guards; short/partial and pit segments
were not exported. No session was filtered by lap number.

## Geometry (entry / apex / exit, metres)

| Corner | Before | Now |
|---|---|---|
| Copse | 206 / 368 / 372 | 221 / 363 / 364 |
| Maggots | 790 / 828 / 833 | unchanged in full |
| Becketts | 884 / 1046 / 1086 | 894 / 1059 / 1076 |
| Brooklands | 1746 / 1925 / 1957 | 1748 / 1921 / 1944 |
| Luffield | 2003 / 2092 / 2103 | 2009 / 2107 / 2129 |
| Woodcote | 2360 / 2469 / 2580 | unchanged in full |

The four detected brake events were reviewed against actual controls and
steering; all movements are ≤26 m. The guarded command used a 30 m bound:

```bash
PYTHONUTF8=1 .venv/Scripts/python.exe dev/scripts/update_reference_and_coaching_model.py \
  --session sessions/session_20261115T095239Z_silverstone-national-circuit_lmu_quali.parquet \
  --track-id silverstone-national-circuit --min-lap-time-s 30 \
  --preserve-geometry maggots woodcote --max-geometry-delta-m 30
```

All six official names, stable IDs, manual sides and other non-geometry corner
fields survived. Maggots and Woodcote retained **their entire objects**, including
100% targets; actual throttle minimum 1.0 and brake maximum 0.0 across both zones.
Model simulator axis remains 2639.1 m. A second identical command wrote nothing.

## Verification

- Test-first: updated expectations failed on the old assets (11 reported failures
  including the Node wrapper); the guarded data update made them pass.
- `--feature track-outline`: 1,386 assertions / 32 scripts, pass (5 browser
  scripts skipped during this fast run).
- `--feature session-debrief`: 809 assertions / 25 scripts, pass (1 browser
  script skipped during this fast run).
- Full `bash scripts/test-summary.sh --pw`: **2,965 assertions / 100 scripts**, pass.
- Reference validator: **38 references, 0 failures**, new lap traced to source.
- `--print-facts`: qualifying lap 9 vs new ref gives **+0.180 s**, correct named
  corners; reference vs itself gives **0.000 s**, no gains/losses.
- `npm run build`: succeeds; `product/dist/compare.html` matches the committed
  bundle, so no distribution change is needed.
- Hash audit: only one reference superseded, plus this combo's JSON/diagnostics;
  183 other audited files (including source inputs) byte-identical. P3 assets,
  outline, TinyPedal/map assets and vehicle catalog unchanged.

Raw check outputs and before/after audit are in `artifacts/`. Existing feature
lists already cover all touched paths, so no package.json change was needed.
No new runtime helpers, production algorithm changes or feature flags.

## Deferred / next action

- Copse exit remains a throttle-onset boundary, now 1 m after the detected apex
  (previously 4 m). This is the known slice-52/53 detection limitation, not a
  newly curated physical exit. Do not infer a long physical exit zone from it.
- Restart the coach to load the new reference/model. Existing saved debriefs
  still use the old baseline; rerun explicitly if a new evaluation is wanted.
- Rear-slip slices were **not** started or changed. User wants to return to
  that work after this delivery, but this slice stops here. Prior rear-slip
  planning edits and `coach-race.log` remain outside this commit.
