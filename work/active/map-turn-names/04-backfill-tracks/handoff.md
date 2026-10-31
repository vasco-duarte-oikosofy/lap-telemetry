# Handoff — Slice 04 (backfill `turns` for every outline)

## State on disk

- **14 of 22 outlines now carry a `turns` block**: Imola, Interlagos, Barcelona,
  La Sarthe, Daytona, Fuji Classic, Road Atlanta, Monza Curva Grande,
  Paul Ricard 1A-V2-Short, Paul Ricard 3A, Sebring, Silverstone GP,
  Silverstone International, Laguna Seca.
- The other 8 are **skipped by design** and listed with reasons in
  `artifacts/BACKFILL.md`: 6 models are uncurated placeholders (full Monza,
  Bahrain, Bahrain Outer, COTA, Lusail, Spa — Spa has 69 corners!), 3 outline
  files have no coaching model at all (legacy/alternate slugs).
- `short_name` added to 9 coaching models (37 corners total). This is
  display-only data: `name` is untouched, so the coach still says
  "Curva Alboreto (Parabolica)" while the map shows `T10 Parabolica`.
- Every static ES module for those 14 tracks regenerated
  (`dev/scripts/generate_outline_module.js`), `dist/compare.html` rebuilt.
- `dev/scripts/bake_outline_turns.py` `unwrap_lap()` fixed to **sort by
  distance** instead of rolling at the first descent (see learnings).
- `dev/scripts/lib/outlineTurns.js` now tolerates a non-JSON existing file
  (regression caught by `test_compute_boundaries.js`, which writes a SENTINEL
  file to prove `--overwrite`).
- `test_outline_turns.js`: `KNOWN` extended to all 14 tracks and now asserts
  `short_name` agreement with the model (39 assertions).

## Measured placement at 250 px (slice-01 harness)

| Result | Tracks |
|---|---|
| all labels shown with names, no overlap | Interlagos, Daytona, Road Atlanta, Monza CG, Silverstone GP, Silverstone International, Laguna Seca |
| 1–2 labels fall back to `T<n>` (chained apexes) | Imola (T3, T10), Fuji Classic (T1, T9), PR 1A-V2-Short (T5), PR 3A (T1), Sebring (T10) |
| 1 label dropped (chained apex) | La Sarthe (T13), and T19 shows as a number |

Zero string overlaps everywhere; mean apex→label-box distance 2.5–5.1 px.

## Commands

```bash
python3 dev/scripts/bake_outline_turns.py --all --check   # staleness report
python3 dev/scripts/bake_outline_turns.py --all           # (re)bake
node dev/scripts/generate_outline_module.js product/data/track-outlines/<slug>.json
node dev/scripts/test_outline_turns.js
bash scripts/test-summary.sh --feature map-turn-names
```

## Review round 2 changes (approved on Le Mans 250 px)

- **Alternating sides** (odd turns outside, even inside) is now the placement
  rule; the opposite side is the first fallback before a label loses its name.
- **Candidate order**: text -> side -> nudge.
- **Nudge caps split**: along-track `2.4 x fontSize`, normal
  `min(2.4 x fontSize, 4 % of mapSize)` so labels cannot drift on small maps.
- **Text tiers**: below 150 px also try `<n> <name>` (drop the `T`).
- **`short_name` curated further**: Interlagos (8), Imola (4), La Sarthe (3) —
  e.g. `Descida do Lago 1` -> `Lago 1`, `Acque Minerali 1` -> `Acque 1`,
  `Dunlop Chicane 1` -> `Dunlop 1`.

Result: **250 px — 14/14 tracks fully labelled with names, zero overlaps.**
120 px — 12/14 complete (Interlagos 15/15, Le Mans 16/19).

## Deferred

- Slice 03 renders these (still nothing reads `turns` in `product/web`).
- Curating names for the 8 skipped tracks is coaching-model work, not this
  mission's rendering work.
- `product/data/track-coaching/spa-francorchamps_*.json` has 69 "corners" —
  worth filing separately; it is unusable as a turn list.
