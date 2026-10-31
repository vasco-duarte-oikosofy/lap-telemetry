# Turn-label placement — algorithm and measurements (slice 01 spike)

Everything below is measured on real data with the scripts in this folder:

```bash
python3 bake_anchors.py silverstone-international-circuit
python3 bake_anchors.py monza-curva-grande-circuit
node render_labels.mjs            # writes labels-<slug>-<tag>.png + overlap-report.json
```

Nothing here is production code. Constants are named so slice 02/03 (and the
TinyPedal port) can copy or change them deliberately.

---

## 1. Bake: name → anchor (per track outline)

For each corner of the curated coaching model:

1. **Position.** Interpolate the reference lap's `pos_x_m` / `pos_z_m` at
   `s = apex_s_m`.

   ⚠️ **`lap_distance_m` in an exported reference parquet WRAPS at the
   start/finish line** — the first row is not `s = 0` (e.g. 2960.68 → … → 0.1 →
   … → 2958.72 for a 2961 m lap). Rolling the arrays at the single wrap point is
   mandatory; a plain binary search on the raw column silently returns a bogus
   bracket (this cost the first spike run and produced `(0,0)` normals).

2. **Track direction** from the lap at `s ± 2 m`, then the two candidate
   normals. Pick the one whose probe point (`p + n·25 m`) is **outside the
   outline centreline polygon** (ray casting). No left/right sign assumption —
   the sim's sign convention is not portable between tracks (slice-13
   learnings).

3. **Gap.** `offset_world = (font_px · 0.9) / scale_250`, where
   `scale_250 = (250 − 2·20) / max(bbox_w, bbox_h)` is the same fit as
   `pipeline.js buildTrackTransform`. Baking a *pixel* gap as a *world* offset
   makes the label keep its relative distance at any map size.

| track | world_per_px @250 | baked gap | turns |
|---|---|---|---|
| Silverstone International (929 × 995 world units) | 4.735 m/px | 35.2 world units = 7.42 px | 8 |
| Monza Curva Grande (1260 × 2167 world units) | 10.32 m/px | 76.6 world units = 7.42 px | 10 |

4. **Display name.** `short_name || name`, prefix `T<number>`; a model name
   matching `/^turn\s*\d+$/i` counts as unnamed → `T<number>` only.

## 2. Render: place the text

- `fontSize = clamp(mapSize · 0.033, 6, 11)` → **8.25 px at 250**, **6 px at 120**.
- `text-anchor` / `dominant-baseline` from the screen-space normal quadrant:
  `|nx| > 0.35` → text grows horizontally away from the track; else centred.
- Then a **resolve pass**, in turn order:
  1. **push** outward along the normal in `step 2 px` up to `+26 px` until the
     label clears (a) labels already placed and (b) the ribbon, with
     `clearPx = 2`;
  2. **clamp** into the viewBox (labels are never allowed to be clipped);
  3. **drop** whatever still collides — reported, never silent.

The order matters: clamp *after* push, otherwise the clamp undoes the push for
labels near the map edge (that is why an earlier "push-only" run at
`maxPushPx = 26` recovered nothing).

## 3. Measurements (250 px canonical map, and 120 px TinyPedal-size)

`overlap` = intersecting label rects; `clear` = min distance from a label rect
to the ribbon/centreline; `dropped` = labels suppressed by the resolve pass.

### Silverstone International — 8 turns, 4.74 m/px

| config | font | shown | overlaps | dropped | widest | mean |
|---|---|---|---|---|---|---|
| raw, official names | 8.25 | 8 | **1** (T1×T2, 152 px²) | 0 | 53.2 px | 37.4 px |
| raw, short names | 8.25 | 8 | 1 (T1×T2) | 0 | 53.2 px | 37.4 px |
| push+clamp+drop, official | 8.25 | 7 | 0 | T2 Farm Curve | 42.6 px | 35.1 px |
| push+clamp+drop, **numbers only** | 8.25 | **8** | 0 | none | **10.4 px** | 10.1 px |
| 120 px, short names | 6 | 5 | 0 | T4, T5, T7 | 38.7 px | 27.4 px |
| 120 px, **numbers only** | 6 | **8** | 0 | none | 8.1 px | 8.0 px |

Also: at 250 px, **2 of 8 labels were clipped** by the raw placement (T5
Becketts, T8 Club) — the 20 px map padding is not enough room for a 35–53 px
label pushed outward. The clamp fixes it.

### Monza Curva Grande — 10 turns, 10.32 m/px

| config | font | shown | overlaps | dropped | widest | mean |
|---|---|---|---|---|---|---|
| raw, official names | 8.25 | 10 | **2** (Roggia 1×2 698 px², Ascari 1×2 474 px²) | 0 | **113.1 px** | 73.3 px |
| raw, short names | 8.25 | 10 | 2 (same pairs, 315 / 261 px²) | 0 | 60.2 px | 44.2 px |
| push+clamp+drop, official | 8.25 | 8 | 0 | T3 Roggia 2, T8 Ascari 2 | 113.1 px | 71.0 px |
| push+clamp+drop, short | 8.25 | 8 | 0 | T3 Roggia 2, T8 Ascari 2 | 60.2 px | 44.8 px |
| push+clamp+drop, **numbers** | 8.25 | **9** | 0 | T3 | 13.5 px | 10.5 px |
| 120 px, short | 6 | 5 | 0 | T2, T3, T5, T8, T9 | 43.6 px | 34.3 px |
| 120 px, numbers | 6 | 7 | 0 | T3, T6, T9 | 10.3 px | 8.3 px |

## 4. What the numbers say

1. **Official names do not fit.** Monza's mean label is 73 px on a 250 px map
   (29 % of the width) and the widest — `T10 Curva Alboreto (Parabolica)` — is
   113 px (45 %). Short display names cut the width by **~45 %** for no loss of
   information (the official name stays in the coaching model).
   → the `turns` schema needs an optional `short_name`.

2. **Chained sub-turns cannot be labelled individually — this is geometry, not
   tuning.** Roggia 1 and Roggia 2 apexes are 44 m apart = **4.3 px** on the
   map at 250 px; Ascari 1/2/3 are 96 m and 98 m = **9.3 / 9.5 px**. Even
   `T2` / `T3` (10 px wide) collide there. Pushing cannot fix it: both labels
   sit on nearly the same normal ray, so one must be pushed off the map, and the
   clamp pulls it back into the collision.
   → either accept the drop (1–2 labels per chicane complex) or, better, render
   **one label per chain** (`Roggia`, `Ascari`) chosen at bake time with a
   `chain_id`; the chain's members stay in the model and in the coach.

3. **Numbers-only is a viable small-map mode.** At 120 px, names survive for
   only 5 of 10 corners; numbers survive for 7–8 of 10 and are 8–10 px wide.
   → degradation rule by map size (validated at 250 and 120):
   `≥ 200 px` → `T<n> <short_name>`, `150–200 px` → `T<n> <short_name>` with
   `fontRatio 0.026`, `< 150 px` → `T<n>` only.

4. **A fixed pixel gap of ~0.9 × font is too tight.** Raw placement leaves
   ~0.03 px clearance to the ribbon: the text box starts exactly at the ribbon
   edge. The push pass raises it to 2.12 px. If the push pass is kept, the
   baked gap can stay at 0.9 × font; if we want raw placement to be acceptable,
   the gap must grow to ~1.4 × font.

5. **Padding, not font size, is what causes clipping.** The map keeps its 20 px
   padding (as `pipeline.js` does) while labels are placed outside the ribbon.
   Clamping into the viewBox is enough; no need to change the track transform
   (which would shrink the track and break the existing acceptance tests).

## 5. Recommendation for slices 02–03

**Bake (slice 02):** unwrap-aware anchor bake as above, plus two new optional
fields per turn — `short_name` (curated, display only) and `chain_id` (bake-time
grouping of corners < 150 m apart). Validation: finite anchors inside the
outline bbox, `number` unique and 1-based, chain members contiguous.

**Render (slice 03):** exact transform reuse; text `T<n> <short_name || name>`;
one label per `chain_id`; resolve pass = push → clamp → drop; map-size
degradation per finding 3. Feature flag ON by default; no labels when the
outline has no `turns`.

**Portability (TinyPedal):** everything above is expressed in map pixels and
multiples of `fontSize` — no 250, no DOM. The only browser-specific step is
measuring text width (`getBBox`); the Qt equivalent is `QFontMetrics`.
`MAP_PAD` maps to `area_margin`, the map size to `area_size` (min 100 px there,
so the numbers-only mode is the realistic default), and the 5 constants to carry
over are `FONT_RATIO 0.033`, `FONT_MIN 6`, `FONT_MAX 11`, `GAP_RATIO 0.9`,
`clearPx 2`, `maxPush 26 px`, `step 2 px`.
