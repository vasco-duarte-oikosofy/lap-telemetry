# Learnings — Slice 54 (Paul Ricard ELMS / F296, race refresh)

## A faster lap makes the detector *worse*, not better

The 2:06.440 lap is 1.161 s faster than the 2:07.601 reference, and it yields
**10 braking events for 16 curated corners** (the slower reference yielded 11).
The missing six are not corners the driver suddenly stopped braking for — they
are three chained complexes the detector merged into single events:

| complex | merged event | halves |
|---|---|---|
| Hôtel + Camp | 1184 → 1539, apex 1507 | `hotel_1` (1307), `hotel_2` (1411), `camp` (1521) |
| Beausset | 4178 → 4512, apex 4379 | `beausset_1` (4390), `beausset_2` (4482) |
| Lac + Pont | 5182 → 5492, apex 5473 | `lac` (5380), `pont` (5470) |

Nearest-first matching (bug 29) correctly hands each merged event to the nearest
apex, so the *first* half of each pair matched and the second did not. The trap
is that "matched" is not the same as "sane": the merged span's **boundaries**
are the neighbour's boundaries. Taking Camp's match literally would have moved
its entry from 1462 to **1184** — 278 m of Hôtel inside the Camp zone.

`--max-geometry-delta-m 40` caught it, which is exactly what the flag is for.
**Lesson: always run the geometry guard on a refresh; a merged event produces a
matched corner with a nonsense boundary.** The rule of thumb that follows: if a
corner's event span starts inside its predecessor or ends inside its successor,
preserve the whole cluster rather than adopting the span.

## A `--preserve-geometry` run cannot undo an earlier refresh

Second run of the slice, I passed `--preserve-geometry … bendor` and the updater
answered `Coaching model already up to date - nothing written`, leaving Bendor's
*already-refreshed* geometry in place. That is correct behaviour — "preserve"
means "keep what the file says now", and the file said 4675/4809/4847. To revert
a corner to reviewed geometry you must restore those numbers first (here: copy
from `artifacts/model-before.json`), *then* run with the corner preserved.

## The map-label gate is a real constraint on model geometry

Bendor's refreshed apex (4809 vs 4831) moved its `s_frac` enough that TinyPedal's
label planner could not keep the name at 400 px / 0° — it fell back to `T13`, so
the sibling widget test failed its "at most one number-only fallback" gate even
though the label count (15/16) and overlap checks still passed.

Two honest options exist; this slice took the second:

1. Relax the label gate (weakens a legibility contract in a sibling repo).
2. Keep the reviewed geometry for a 22 m change that buys nothing measurable.

The second is defensible *because* the change was flagged by the default guard
anyway, but the general point is worth carrying forward: **coaching-model apices
are also map-label anchors**, so a "harmless" 20 m apex refresh can cost a
readable name on the densest overlay. Check the label test, not just the data
test, after any refresh on a track with 16 turns at 400 px.

## The outline is `STALE` for two different reasons

`bake_outline_turns.py --check` says STALE for this track both before and after
this slice. The *alias* reason is permanent: a fresh bake writes
`short_name: "Sainte-Baume"`, the outline carries the map-only alias `Ste-Baume`.
Re-baking must therefore go through the compact writer + alias re-application
(`artifacts/rebake_outline.py`), not through `bake_outline_turns.py <slug>`,
which would also rewrite the file with `indent=2` (~6000 lines, past the 437
hard ceiling). Confirm pre-existing STALE by checking the committed pair before
blaming your own change.

## Small mechanics

- A finalized race (`in_progress: false`, `ended_utc` set) needs no freeze — the
  `partN` shards only appear for recordings that are still open. Always read the
  sidecar before reaching for `freeze_source.py`.
- `export_turn_labels_for_tinypedal.py --check` prints `up to date: 1
  turn-label files`; the sibling repo (`../tinypedal`) is a separate git
  work-tree, so its label file is a *second* commit to make.
- `py dev/scripts/validate_reference_laps.py` counts 38 references after the
  swap — the superseded 2:07.601 file is deleted by the guarded exporter, so the
  count stays flat.
