# Handoff — Slice 45 (Fuji Speedway base turn labels in TinyPedal)

## Symptom → cause

| | |
|---|---|
| Symptom | The `Fuji Speedway` map in TinyPedal draws no turn names (the `Fuji Speedway Classic` map does). |
| Cause | The base outline had no `turns` block, so the exporter skipped it. The baker only looks for `<slug>.json`; this legacy outline is `fuji-speedway_outline.json`. |
| Same-class risk | `bahrain_outline.json` and `circuit-de-barcelona-median.json` are also legacy-named, but they are not the manifest source for their tracks, so nothing is missing there today. |

## Files changed — `lap-telemetry`

| File | Change |
|---|---|
| `dev/scripts/bake_outline_turns.py` | new `outline_file_for(slug)` resolves `<slug>.json`, falling back to `<slug>_outline.json` |
| `dev/scripts/test_outline_turns.js` | `LEGACY_OUTLINE_FILES` map; pins `fuji-speedway` names/apexes/display labels (failed before the bake) |
| `product/data/track-outlines/fuji-speedway_outline.json` | `turns` block (11 turns) + `lap_length_m: 4538.9` |
| `product/web/js/staticFujiSpeedway_outlineOutlineData.js` | regenerated from the outline (same export name) |
| `product/dist/compare.html` | rebuilt |

Nothing else in the outline changed except its serialisation: the bake writes
with `ensure_ascii=False`, so two `caveats` lines now contain a literal em dash
instead of `\u2014` (`write_turns` claims byte-identical output; it is not, for
escaped characters — same JSON value).

## Files changed — `tinypedal`

| File | Change |
|---|---|
| `tinypedal/data/turn_labels/Fuji Speedway.turns.json` | **new**, 11 turns, `lap_length_m 4538.9` |

## The 11 labels on the base map

| Map number | Official name | Displayed text |
|---|---|---|
| T1 | First Corner | `First` |
| T2 | Coca-Cola | `2` |
| T3 | 100R | `One Hundred R` |
| T4 | Hairpin | `4` |
| T5 | Dunlop Bypass | `Dunlop` |
| T6 | Turn 11 | `Eleven` |
| T7 | Turn 12 | `Twelve` |
| T8 | 13th Corner | `Thirteenth` |
| T9 | Netz | `9` |
| T10 | Netz Hairpin | `Netz Hairpin` |
| T11 | Panasonic | `11` |

`T6`/`T7` have `name: null` because the shared placeholder rule (`^turn \d+$`)
treats the official "Turn 11"/"Turn 12" as a generated name; their curated
`short_name` (`Eleven`/`Twelve`) keeps the official information on the map, and
the coaching model still speaks "Turn 11". If that ever reads oddly on the map,
curate the outline `name` to `11th Corner`/`12th Corner` — a data change, not a
code change.

## Verified

- `bake_outline_turns.py fuji-speedway` → `baked fuji-speedway: 11 turns (9/11 named)`.
- `export_turn_labels_for_tinypedal.py --track "Fuji Speedway"` → wrote 11 turns;
  `--check` exits 0.
- `node dev/scripts/test_outline_turns.js`: 43/43 assertions pass (was 41/42 with
  the new Fuji check failing before the bake).
- `bash scripts/test-summary.sh --feature track-outline`: 952 assertions pass.
- Full `--pw` suite: 2029 assertions over 80 scripts pass.
- `npm run build` rebuilt `dist/compare.html` (inline outline changed).
- Scope: one outline, one static module, one bundle, one TinyPedal label file.

## Not done / next

- **`Fuji Speedway Classic` labels use the geometric denominator** (4464.5 m)
  while its model axis is 4510.1 m, so its labels sit ~1 % (~45 m) late. Same
  class of bug the Long Beach slice fixed. Fix = stamp `lap_length_m: 4510.1` on
  `fuji-speedway-classic.json` and re-export that one track (a two-line follow-up).
- `bahrain_outline.json` / `circuit-de-barcelona-median.json` are legacy-named
  duplicates; the architecture review already flags the naming. Renaming them to
  the canonical slug (and regenerating modules + manifest imports) is a separate
  refactor, not done here.
- TinyPedal caches labels until a map update: restart TinyPedal or reload the
  track to see the new file.
