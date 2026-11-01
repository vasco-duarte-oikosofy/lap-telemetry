# Slice 12 — Coach speaks curated short corner names

**Mission:** [`../PLAN.md`](../PLAN.md) · **Status:** ✅ Done (`4968f39`) — see `handoff.md` and `learnings.md`

## Outcome

Every coached utterance uses the curated `short_name` when the model has one,
and falls back to `name` when it does not:

| model corner | `name` | spoken today | spoken after |
|---|---|---|---|
| `t2` | Variante della Roggia 1 | Variante della Roggia 1 | **Roggia 1** |
| `t3` | Variante della Roggia 2 | Variante della Roggia 2 | **Roggia 2** |
| `t6` | Curva del Serraglio | Curva del Serraglio | **Serraglio** |
| `t9` | Variante Ascari 3 | Variante Ascari 3 | **Ascari 3** |
| `t10` | Curva Alboreto (Parabolica) | Curva Alboreto (Parabolica) | **Parabolica** |
| `t4` | Lesmo 1 | Lesmo 1 | Lesmo 1 (no short name) |

## Why now

`short_name` already exists in `product/data/track-coaching/*.json` and is
curated by hand, but only the map/turn-label code reads it
(`web/js/turnLabels.js`, `dev/scripts/bake_outline_turns.py`). The coach's
`Corner` dataclass has no such field, so `load_track_coaching_model()` throws
the value away and every utterance says the long official name — awkward in
speech after a corner ("Variante della Roggia 2") and needlessly long for TTS.

## Steps

1. Write the failing test: `dev/scripts/test_coach_short_names.py`.
2. Add `short_name` to `Corner` (optional, `None` = no short name) plus a
   `display_name` property that prefers it — the single naming rule.
3. Load it in `validate_corner` (absent key → `None`, so every existing model
   keeps working unchanged).
4. Use `display_name` at the two places a corner reaches the driver:
   `lap_comparator` (`CornerLoss.corner_name`, 3 sites) and
   `CornerExitDetector._emit` (`CornerExited.corner_name`).
5. Add the feature test list `coach-short-corner-names` to `package.json`.
6. Run `bash scripts/test-summary.sh --feature coach-short-corner-names`, then
   the full suite with `--pw`, then `npm run build`.
7. Commit, write `handoff.md` + `learnings.md`.

## Out of scope

- Curating `short_name` for tracks that do not have one yet (Barcelona, Fuji,
  Silverstone, …). The coach must simply fall back to `name`.
- Changing `corner_id` (stable identity, never spoken) or the facts JSON shape.
- Any change to the map/turn-label naming path — it already works.
