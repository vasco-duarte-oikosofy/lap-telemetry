# Handoff — Slice 51: Silverstone National Circuit / Ginetta P3 (new combo)

## Result

- **Reference** `product/data/reference-laps/silverstone-national-circuit_dkr-engineering-4-elms25_time_00.50.446.parquet`
  — practice lap **20** of `session_20261111T173251Z_silverstone-national-circuit_lmu_practice`
  (DKR Engineering #4:ELMS25 → catalogued slug `ginetta-lmp3`), authoritative
  **50.446 s**, **2512 rows**, single contiguous segment, valid throughout.
  Onboarded from the first stint at **50.859 s** (`…_time_00.50.859.parquet`,
  lap 7 of `session_20261111T172218Z`) and refreshed to the second stint's lap 20;
  the exporter's audit reported one added and one superseded reference both times.
- **Model** `product/data/track-coaching/silverstone-national-circuit_dkr-engineering-4-elms25.json`
  (+ `.diagnostics.txt`) — **6** curated zones, `layout_id: national`,
  `lap_length_m` **2639.1** (simulator axis). Official Silverstone National names:
  `Copse`, `Maggots`, `Becketts`, `Brooklands`, `Luffield`, `Woodcote`.
  Sides: Copse R, Maggots **L**, Becketts R, Brooklands **L**, Luffield R, Woodcote R.
  Two flat bends carry `target_throttle_pct: 100`: **Maggots** (790/836/850) and
  **Woodcote** (2360/2469/2580) — both verified throttle 1.00 / brake 0.00 across
  the zone on the reference lap. Copse (peak brake 0.38) and Becketts (0.71) are
  real braking corners and are *not* marked flat.
- **Outline** `product/data/track-outlines/silverstone-national-circuit.json` —
  500 centreline points, 500 per synthetic ±5 m boundary, 6 turn anchors on the
  `lap_length_m` axis, compact-formatted (351 lines). Module
  `product/web/js/staticSilverstoneNationalCircuitOutlineData.js`, manifest key
  **`silverstone-national-circuit`**.
- **TinyPedal** — packaged `tinypedal/data/turn_labels/Silverstone National Circuit.turns.json`
  (6 turns, `s_frac = apex / lap_length_m`, `--check` clean). New sibling-repo
  widget test `tinypedal/tests/test_silverstone_national_turn_labels.py`: anchors
  worst **20.8 m**, 6/6 labels at 400/600 px × 0/90°, zero overlaps, every label
  changes real widget pixels, every label carries its name (no number-only
  fallbacks). The recorded `trackmap/Silverstone National Circuit.svg` already
  started at the timing line (axis 0.0 m, position 10.3 m) — nothing to rotate.
- **Bundle** rebuilt: `product/dist/compare.html` (140 lines). File-replay
  evidence `var/test-output/silverstone-national-p3/outline.png`: three outline
  parts paint and all six labels render (`test_silverstone_national_p3_ui.js`).

## Layout identity (why this is not International or GP-ELMS)

The National lap follows the curated GP-ELMS reference line within **9 m**
everywhere except one National-only link at 1090–1180 m (max **35 m**) between
the Maggots flick and the Wellington Straight. It therefore has:
Copse (382), Maggots (836), Becketts (1045) → Wellington Straight (nothing for
1.1–1.7 km) → Brooklands (1906), Luffield (2084), Woodcote (2469). No Abbey /
Farm Curve / Village / The Link (Arena), no Becketts complex left, no Hangar
Straight, no Stowe / Vale / Club. Simulator axis 2639.1 m vs TinyPedal's recorded
map axis 2630.2 m.

## The 60 s lap floor (new guard flag)

The guarded exporter had `MIN_LAP_TIME_S = 60.0` as a hard wall; a 2.64 km
National lap is ~51 s, so **every** lap of this combo was rejected. Both
`export_fastest_reference_laps.py` and `update_reference_and_coaching_model.py`
now take an explicit, validated `--min-lap-time-s` (default unchanged at 60 s;
the updater forwards it to the delegated export). Pinned in
`test_silverstone_national_p3.py::test_exporter_floor`: the default floor yields
zero laps, `--min-lap-time-s 30` yields the ten complete laps of the first stint.

## Refresh provenance (second stint)

`artifacts/reference-refresh.txt` + `artifacts/signal-review.txt`:

| corner | before | after | why |
|---|---|---|---|
| Copse | 242/359/435 | preserved | new lap is at full throttle from ~370 m, so the detector's exit collapses to 369 m — 4 m after the apex (throttle modulation). Exit spreads 363–476 m over 21 clean laps |
| Maggots | 790/836/860 | 790/836/**850** | flat left, no event to refresh; exit hand-corrected so it chains with Becketts' refreshed entry (854 m) without overlap |
| Becketts | 861/1045/1110 | 854/**1067**/1091 | matched, +22 m apex |
| Brooklands | 1744/1906/1955 | 1746/**1924**/1960 | matched, +18 m apex |
| Luffield | 2003/2084/2190 | 2003/**2105**/2168 | matched, +21 m apex |
| Woodcote | 2360/2469/2580 | preserved | flat right, no event to refresh |

All names, ids, `apex_side`, `apex_side_source` and both `target_throttle_pct:
100` markers are byte-identical to the onboarding pass.

## Safe selection

Source hashes before/after are in `artifacts/before-hashes.txt` /
`artifacts/after-hashes.txt` (unchanged). `artifacts/session-scan.txt` lists
every segment of the three practice stints; nothing is selected by
`lap_number`. `artifacts/reference-guard.txt`: re-running the updater across
both practice stints + the garage stint + the quali session reports
`Not faster than existing reference 50.446s - reference stays` and
`Coaching model already up to date - nothing written`.

**The 18:03 race session is still in progress** (24 closed `snapN` shards, no
canonical parquet). Its best complete lap is lap 11 at **50.638 s**, still slower
than the reference (`artifacts/in-progress-race-scan.txt`). If it finishes with a
faster lap, re-run the guarded updater over the merged shards — one command:

```bash
py dev/scripts/update_reference_and_coaching_model.py \
  --session <merged race parquet> --track-id silverstone-national-circuit \
  --preserve-geometry copse maggots woodcote --min-lap-time-s 30
```

then re-bake anchors, rebuild, re-export the TinyPedal labels (see below).

## New helpers worth knowing

- `dev/scripts/create_silverstone_national_p3_assets.py` — **one-shot
  initializer**, not a general tool. Asserts the detector produced exactly the
  reviewed 4 event apexes `[358, 1045, 1906, 2084]`, refuses any reference other
  than the guarded onboarding file, refuses to overwrite differing curation, and
  refuses a file above 437 lines. It also exports `compact_outline()`, which is
  what keeps the outline at 351 lines instead of the ~6000 a plain
  `json.dumps(indent=2)` re-bake would produce.
- `dev/scripts/test_silverstone_national_p3.py` (+ `.js`, `_ui.js`,
  `_tinypedal.js`) — all registered in `testFeatures.track-outline` and in
  `npm test`.

## Re-baking anchors after a future refresh

`bake_outline_turns.py` rewrites the whole outline with `indent=2` (~6000 lines).
For this track, re-bake in place with the compact writer instead:

```python
from bake_outline_turns import bake_turns
from create_silverstone_national_p3_assets import compact_outline, TRACK
# outline['turns'] = bake_turns(TRACK, outline, {'corners': model['corners']}, ref)
# then compact_outline(outline) -> 351 lines
```

## Tests

- `bash scripts/test-summary.sh --feature track-outline --pw`:
  **1269 assertions / 35 scripts — ALL PASS**.
- Full `bash scripts/test-summary.sh --pw`:
  **2703 assertions / 96 scripts — ALL PASS** (`artifacts/full-suite.txt`).
  One earlier run showed `test_bug_python_regressions.js` failing under the
  parallel runner; it passes standalone and on the re-run (runner flake).
- `--print-facts` on lap 21 (50.711 s, +0.265 s): every corner id resolves,
  top losses are Copse exit throttle / minimum speed (`artifacts/lap21-facts.json`).

## Scope

`artifacts/scope-audit.txt`: only this slice's four new curated files, the
manifest, the static module, the bundle, the coverage doc, the PLAN, the two
guarded-script flag changes and the new scripts changed. 36 other reference
laps, 74 other coaching files and 28 other outlines are untouched.

## User action / remaining work

- **Restart the coach** and reload TinyPedal's map so the new reference, model
  and packaged label file are picked up (the superseded 0:50.859 reference no
  longer exists).
- **Live by-eye approval is still pending** — `visual_qa.status` is `pending`;
  the automated `file://` render is not human approval.
- Deferred TODOs:
  - Copse's apex/exit is a wide, flat speed minimum on this car (apex wanders
    358–470 m across clean laps). If the coach's Copse apex offsets feel noisy,
    the fix is a curvature-based apex rather than the speed minimum.
  - The centreline is the onboarding lap's racing line (0:50.859); it was kept
    stable through the refresh. Regenerating it from the current reference is a
    one-liner with `create_silverstone_national_p3_assets.make_outline` if the
    map shape ever matters more than the churn.

## Untouched on purpose

- Silverstone GP-ELMS and International references, models, outlines and labels.
- Every other track's reference, model, outline and TinyPedal labels.
- `coach-race.log` at the repository root (live coach runtime artifact).
- `product/web/js/trackOutlineManifest_backup.js` (stale backup flagged in the
  architecture review; reverted after `register_outline.py` rewrote it).
