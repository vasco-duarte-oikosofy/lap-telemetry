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
