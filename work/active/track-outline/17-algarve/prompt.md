# Slice 17 — Algarve International Circuit (Portimão), trajectory outline

## Trigger

`product/data/` already holds two curated Algarve assets — a reference lap and a
coaching model for `(algarve-international-circuit, dkr-engineering-4-elms25)`
(1:40.706) and for `(algarve-international-circuit, vista-af-corse-2025-21-lm)`
(1:46.279) — but the track has **no outline**: no
`product/data/track-outlines/algarve-international-circuit.json`, no static ES
module, no `trackOutlineManifest.js` entry. Every compare.html session on that
track renders a blank map.

This is the first remaining `track-outline` row that can be completed from data
already in the repository: the tracks listed before it in `PLAN.md`
(Bahrain Endurance/Paddock, COTA National, Le Mans no-chicanes) have no session
data on this machine, and COTA GP / Le Mans / Lusail / Sebring already have
outlines despite stale table rows.

## Goal (one vertical outcome)

`(algarve-international-circuit)` renders in `compare.html` with a trajectory
outline traced from the committed reference lap, registered like every other
trajectory outline: JSON in `product/data/track-outlines/`, static module,
manifest entry, `dist/compare.html` rebuilt, tests green.

## Data

| source | use |
|---|---|
| `product/data/reference-laps/algarve-international-circuit_dkr-engineering-4-elms25_time_01.40.706.parquet` | centreline (fastest committed lap, 5 023 rows, `lap_length_m` 4633.1, the same axis as the DKR model) |
| `product/data/reference-laps/algarve-international-circuit_vista-af-corse-2025-21-lm_time_01.46.279.parquet` | independent cross-check only (different car, +5.6 s) — measures how far a second driver's line sits from the shell |

No TUMFTM data (no `Austin.csv`-style CSV for Portimão in the repo), so this is
`source: Single lap trajectory`, ±5 m constant shell, per
[`dev/scripts/GENERATE_TRAJECTORY_OUTLINE.md`](../../../dev/scripts/GENERATE_TRAJECTORY_OUTLINE.md).

## Execution

1. Freeze the two reference laps (verify full coverage: `lap_distance_m` min ≈ 0,
   max ≈ lap length, single `lap_number`).
2. Generate the outline JSON (500 points, ±5 m) from the DKR lap, `pos_x_m` /
   `pos_z_m`.
3. Measure the Vista lap's line against the centreline; record the distribution
   in `alignment.notes` and in `artifacts/`. If p95 deviation exceeds the ±5 m
   shell, say so in `caveats` — the shell then under-states the line variation.
4. `python3 dev/scripts/register_outline.py product/data/track-outlines/algarve-international-circuit.json`
   (validates, writes `staticAlgarveInternationalCircuitOutlineData.js`, wires
   `trackOutlineManifest.js`, rebuilds `dist/compare.html`).
5. `bash scripts/test-summary.sh --feature track-outline --pw`.
6. Update `docs/TRACK_OUTLINE_COVERAGE.md` (coverage table) and this mission's
   `PLAN.md` row, with the commit hash.

## Non-goals

- **No turn labels and no turn anchors.** Both Algarve coaching models carry
  auto-generated names (`Turn 1…15`, and a 9-corner legacy model whose apexes are
  all `right`); baking those as map labels would be noise. Curating Portimão's
  official corner names is a separate slice on the model, not on the outline.
- No reference-lap or coaching-model change — both are curated, guarded assets.
- No `18-algarve-elms` decision beyond recording the evidence: both references
  share `track_id = algarve-international-circuit`, so one outline serves both
  layouts **if** the ELMS pack really is the same 4.6 km GP layout; confirm from
  the two models' `lap_length_m` (4633.1 / 4638.7 m) and note it in `handoff.md`.

## Acceptance

- [ ] `product/data/track-outlines/algarve-international-circuit.json` exists,
      validates, and its `track_name_mapping` resolves the LMU track name.
- [ ] `product/web/js/staticAlgarveInternationalCircuitOutlineData.js` exists and
      `trackOutlineManifest.js` imports it.
- [ ] `npm run build` succeeds; `dist/compare.html` contains the outline data.
- [ ] `bash scripts/test-summary.sh --feature track-outline` exits 0.
- [ ] `learnings.md` + `handoff.md` written; `PLAN.md` row and
      `docs/TRACK_OUTLINE_COVERAGE.md` updated.
