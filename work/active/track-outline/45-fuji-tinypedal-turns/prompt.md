# Slice 45 — Fuji Speedway (base) turn labels for TinyPedal

Status: ✅ Complete (see git log for this slice)
Trigger: *"the FUJI turn names for TinyPedal … the names don't show up in the map"*.

## Diagnosis

TinyPedal's packaged data carried `Fuji Speedway Classic.turns.json` (9 turns)
but nothing for the **base** `Fuji Speedway` map, so that map drew no names.

The base outline `product/data/track-outlines/fuji-speedway_outline.json` had
**no `turns` block at all**, and `export_turn_labels_for_tinypedal.py` only
exports outlines that already carry curated turns. Why it was never baked:
`bake_outline_turns.py` resolves an outline as `<slug>.json`, and this legacy
file is `<slug>_outline.json` — the baker skipped it as "no outline" for years.
The Classic layout has a canonical file name, which is why its labels exist.

## Deliverables

1. Baker resolves legacy `<slug>_outline.json` (so `bake_outline_turns.py
   fuji-speedway` works and the gap cannot silently recur).
2. Fuji base outline gets its `turns` block from the curated model
   (`fuji-speedway_dkr-engineering-4-elms25.json`, 11 official names).
3. Outline stamps `lap_length_m: 4538.9` (the model's simulator axis), because
   the geometric centreline is 4489.5 m and would place later labels ~1 % late.
4. `tinypedal/tinypedal/data/turn_labels/Fuji Speedway.turns.json` exported (11
   turns), `--check` clean; static module + `dist/compare.html` regenerated.
5. `test_outline_turns.js` now pins Fuji base (names, apexes, display labels)
   and knows about legacy outline file names — it failed before the bake.

## Boundaries

- Only the Fuji base layout: no other outline, model, reference or label file.
- No name curation: the 11 names come from the existing curated model.
- `Fuji Speedway Classic` labels are untouched (a known ~1 % axis mismatch
  there is recorded in the handoff as a deferred, separate fix).
