# Handoff — Slice 02 (`turns` block + preservation guard)

## What is on disk

| Path | What changed |
|---|---|
| `dev/scripts/bake_outline_turns.py` | **new** — bakes `turns` into an outline JSON from the curated coaching model + its reference lap. `--all`, `--check`, one slug, or no args (all). |
| `dev/scripts/lib/outlineTurns.js` | **new** — `readExistingTurns`, `withPreservedTurns`: the preservation guard used by every JS outline writer. |
| `dev/scripts/prepare_all_outlines.js`, `auto_align_outline.js`, `compute_boundaries.js` | write outlines through `withPreservedTurns(...)`. |
| `dev/scripts/average_trajectory_outline.py` | `preserve_turns()` + call before writing. |
| `dev/scripts/register_outline.py` | `validate_turns()`: rejects non-1..n numbering, placeholder names, non-finite/outside-bbox anchors, non-unit or non-perpendicular `outward`/`tangent`. |
| `dev/scripts/test_outline_turns.js` | **new** — 12 assertions: helper behaviour, static wiring guard for all four writers, schema validity of every baked block, model agreement, ES-module parity. |
| `product/data/track-outlines/silverstone-international-circuit.json` | now carries `turns` (8 entries, names Abbey … Club, `short_name: null`). |
| `product/web/js/staticSilverstoneInternationalCircuitOutlineData.js`, `product/dist/compare.html` | regenerated (module parity; the bundle is unchanged in behaviour — slice 03 draws them). |
| `package.json` | `test_outline_turns.js` appended to `scripts.test`; `testFeatures["map-turn-names"]` now has 5 scripts. |

## Bake rules (worth knowing before touching it)

- **Only curated models are baked.** A model whose names are all `turn N`
  placeholders is skipped, because a `T1..Tn` from an over-segmented model would
  be wrong on the map (full Monza 6, Spa 69, COTA 14, Bahrain 13, Lusail 16 are
  all skipped for this reason).
- **Model choice when a track has one model per car**: most curated names, then
  most corners, then alphabetical file — deterministic, and a disagreement
  between the top two is printed to stderr. Daytona picked the 12-corner model
  over the 6-corner one; Barcelona picked the 14-corner/7-named one.
- **Reference lap pairing**: `<slug>_<car>_time_*.parquet` for the chosen model's
  car, else the newest `<slug>_*_time_*.parquet`.
- **`name` placeholders become `null`**, so display falls back to `T<n>`;
  `short_name` is copied verbatim from the model (currently only Monza Curva
  Grande has any, and only in the spike — slice 04 decides which models need
  one).

## Commands

```bash
python3 dev/scripts/bake_outline_turns.py --all --check   # stale/missing report, writes nothing
python3 dev/scripts/bake_outline_turns.py --all           # bake every eligible outline
python3 dev/scripts/register_outline.py product/data/track-outlines/<slug>.json
node dev/scripts/test_outline_turns.js
bash scripts/test-summary.sh --feature map-turn-names
```

## Deferred

- Slice 03 renders them (nothing reads `turns` yet in `product/web`).
- Slice 04 backfills the remaining curated tracks (14 eligible were listed by
  `--check`) and curates `short_name` where official names are too wide.
