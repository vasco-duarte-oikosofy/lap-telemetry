# Learnings — Slice 01 (turn label placement spike)

## The one that cost an hour: `lap_distance_m` wraps

`product/data/reference-laps/*.parquet` (and session parquets) store
`lap_distance_m` **starting just before the start/finish line and wrapping to 0
inside the file** — e.g. 2960.68 → … → 0.1 → … → 2958.72 for a 2961 m lap.
Anything that binary-searches that column must roll the arrays at the single
wrap point first. Symptom when you forget: interpolation "works" but returns the
same sample every time, here producing `(0,0)` outward normals.

## Official turn names do not fit on a 250 px map

- Monza Curva Grande: mean label **73 px**, widest `T10 Curva Alboreto
  (Parabolica)` **113 px** — 45 % of the map width, for one corner.
- Silverstone International: mean 37 px, widest 53 px.
- Short display names (`Curva Alboreto (Parabolica)` → `Parabolica`,
  `Variante della Roggia 1` → `Roggia 1`) cut width **~45 %** with no loss: the
  official name stays in the coaching model. The `turns` schema needs an
  optional `short_name`; do not try to auto-strip prefixes — `Curva Grande`
  would become `Grande`.

## Chained sub-turns are unlabellable, and that is geometry

Measured apex spacing on the 250 px map: Roggia 1→2 **4.3 px**, Ascari 1→2
**9.3 px**, Ascari 2→3 **9.5 px**. Numbers alone are ~10 px wide, so even
`T2`/`T3` collide. Pushing outward cannot fix it because both labels sit on
nearly the same normal ray: pushing one off the map forces the clamp to pull it
back into the collision. The honest options are (a) drop the extra labels (what
the spike does: 1–2 per complex) or (b) render **one label per chain** with a
bake-time `chain_id`. (b) is the recommendation.

## Push → clamp → drop, in that order

First attempt pushed labels outward with a 26 px budget and recovered nothing,
because the push drove edge labels out of the viewBox and the clamp then put
them straight back into the collision. Resolve order that works: push (labels
vs. labels vs. ribbon) → clamp into the viewBox → drop only what still clashes,
and report the drops.

## The 20 px map padding is what clips labels, not the font size

Two of eight Silverstone labels left the 250 px viewBox at font 8.25 px with the
`pipeline.js` padding of 20 px. The fix is clamping, not changing the track
transform — the transform is shared with the outline/heatmap acceptance tests.

## Degradation by map size (validated at 250 and 120 px)

| map | names | numbers |
|---|---|---|
| 250 px | 7/8 (Silverstone), 8/10 (Monza) | 8/8, 9/10 |
| 120 px | 5/8, 5/10 | 8/8, 7/10 |

120 px is TinyPedal's realistic size (`area_size` floor is 100 px), so the
numbers-only mode is what the port should default to below ~150 px.

## Reusable technique for reviewable UI math

Render with Playwright into a PNG at `deviceScaleFactor: 3` and measure real
label boxes with `getBoundingClientRect()` in the same page, then report
`overlaps / clipped / clearance / dropped` as numbers next to the image. The
numbers caught two things the images alone would have made ambiguous
(clipping, and the fact that "clearance ≈ 0" means the text box starts at the
ribbon edge, not that it overlaps the track).

---

# v2 — after the first review

The review rejected v1 on three points: type too large, labels detached from
their corner (T3 was 26 px away on the 120 px map), and any string overlap.
"Closest to what I want" was the **raw** placement, not the resolved one — i.e.
the corner-anchored geometry was right, the type and the collision handling were
not. Rules that came out of it:

- **`FONT_RATIO 0.023`** (5.75 px at 250 px, ~30 % down from 0.033). This alone
  removed most collisions: labels got ~30 % narrower before any other change.
- **Adjacency budget instead of a push budget.** v1 pushed along the normal for
  up to 26 px, which is what threw labels off their corners. v2 caps total
  displacement at `2.4 x fontSize` (≈14 px) and tries **along-track** nudges
  first, so a crowded label slides *beside* its corner rather than away from it.
- **Drop the ribbon-clearance constraint.** Requiring 2 px of clearance from the
  track was the reason labels fled the map centre. Crossed strings are fine; a
  label 20 px from its apex is not.
- **`short_name` is a schema field, not a rendering heuristic.** Auto-stripping
  official names fails (`Curva Grande` -> `Grande`), and the coach must keep
  speaking the official name, so the map gets its own curated field.

Placement result with all four changes (250 px): 8/8 and 10/10 labels, zero
overlaps, every box within 2.9-4.0 px of its apex on average, and only 2-3 of 10
labels needing the smallest nudge.

## Pitfall: `pathlib.write_text` truncates before it encodes

A python one-liner that did `p.write_text(s)` hit a `cp1252` `UnicodeEncodeError`
on a `≈` character **after** the file had been truncated — the spec was left at
0 bytes and had to be restored with `git checkout`. On this machine: pass
`encoding='utf-8'` (or set `PYTHONIOENCODING=utf-8`) for any file containing
non-ASCII.

## Pitfall: `display:none` has no bounding box

The candidate-position search measures every candidate with
`getBoundingClientRect()`. Hidden candidates with `display:none` measure `0x0`,
so every candidate looked "inside the viewBox" and then every label was dropped
by the overlap test — the first v2 run showed `shown=0/8`. Use
`visibility:hidden`, which keeps layout and measurement intact.
