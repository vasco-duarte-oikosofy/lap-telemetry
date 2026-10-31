# Turn-label placement — algorithm and measurements (slice 01 spike, **v2**)

Rules from the v1 review, now implemented:

- type **~30 % smaller** than v1 (5.75 px instead of 8.25 px at 250 px);
- a label must stay **adjacent to its corner** — displacement is capped at
  `2.4 x fontSize` (≈14 px) and sliding *along the track* is preferred over
  pushing away from it;
- **strings never overlap** (hard rule);
- **crossing the track is allowed** — the ribbon-clearance constraint is gone;
- text degrades to `T<n>` before a label is dropped;
- `short_name` added to the `turns` schema.

Reproduce:

```bash
python3 bake_anchors.py silverstone-international-circuit
python3 bake_anchors.py monza-curva-grande-circuit
node render_labels.mjs          # labels-<slug>-<size>.png + placement-report.json
```

Nothing here is production code.

---

## 1. Bake: name -> apex + direction (per track outline)

1. **Position.** Interpolate the reference lap's `pos_x_m` / `pos_z_m` at
   `s = apex_s_m`.

   ⚠️ **`lap_distance_m` WRAPS at the start/finish line** in exported reference
   parquets (2960.68 -> … -> 0.1 -> … -> 2958.72 for a 2961 m lap). Roll the
   arrays at the single wrap point first; a binary search on the raw column
   silently returns one sample (first version produced `(0,0)` normals).

2. **Direction + outward normal** from the lap at `s ± 2 m`. The two candidate
   normals are disambiguated by ray-casting a probe point (`p + n·25 m`) against
   the outline centreline polygon: keep the one that leaves the polygon. No
   left/right sign assumption — the sim's convention is not portable
   (slice-13 learnings).

3. **Bake `x`, `y` = the apex itself**, plus `outward` and `tangent` unit
   vectors. The pixel gap is applied at render time (`gap_px / scale`), so the
   data stays render-size independent.

4. **Display names.** `short_name` (`Curva Alboreto (Parabolica)` ->
   `Parabolica`, `Variante della Roggia 1` -> `Roggia 1`), falling back to
   `name`; a model name matching `/^turn\s*\d+$/i` counts as unnamed.

## 2. Render: place the text

- `fontSize = clamp(mapSize * 0.023, 5, 8)` -> **5.75 px at 250**, **5 px at 120**.
- `gap_px = fontSize * 0.75` -> 4.31 px at 250 (v1 used 7.42 px at 8.25 px type).
- `text-anchor` / `dominant-baseline` from the screen normal quadrant:
  `|nx| > 0.35` starts/ends the text away from the track, else centred.
- **Candidate search, per turn, in turn order:**

  | order | text | position |
  |---|---|---|
  | 1 | `T<n> <short_name>` | raw (`apex + outward * gap`) |
  | 2 | same | nudge `+1.2 x fontSize` along the track |
  | 3 | same | nudge `-1.2 x fontSize` along the normal |
  | 4 | same | nudge `+2.4 x fontSize` along the track |
  | 5 | same | nudge `-2.4 x fontSize` along the normal |
  | 6-10 | `T<n>` only | the same five positions |

  Accept the first candidate whose text box overlaps **no already-placed label**
  and stays **fully inside the viewBox**. If all ten fail, drop the label and
  report it.

  There is deliberately **no ribbon-clearance test**: labels may cross the
  track, which is what keeps them on their corner.

## 3. Measurements

`apex->box` = distance from the apex dot to the label's bounding box (0 would
mean the text sits on the apex); `min gap` = smallest distance between any two
label boxes.

### 250 px — canonical compare-app map

| track | font | labels | overlaps | apex->box mean/max | min gap | numbers-only |
|---|---|---|---|---|---|---|
| Silverstone International (8 turns) | 5.75 | **8/8** | 0 | 2.9 / 5.8 px | 4.1 px | none |
| Monza Curva Grande (10 turns) | 5.75 | **10/10** | 0 | 4.0 / 10.4 px | 4.1 px | none |

Only 3 of 10 Monza labels and 2 of 8 Silverstone labels needed any nudge at all
(the rest sit at their raw spot); the largest nudge is `1.2 x fontSize` ≈ 7 px.

### 120 px — TinyPedal-sized map

| track | font | labels | overlaps | apex->box mean/max | min gap |
|---|---|---|---|---|---|
| Silverstone International | 5 | 8/8 | 0 | 2.6 / 7.4 px | 0.3 px |
| Monza Curva Grande | 5 | 10/10 | 0 | 4.1 / 11.3 px | 0.2 px |
| Monza, font floor off | 2.76 | 10/10 | 0 | 1.6 / 5.0 px | 0.7 px |

## 4. What changed vs v1, and why it works now

| v1 problem | v2 fix |
|---|---|
| Type too large (8.25 px) | `FONT_RATIO 0.023` -> 5.75 px: labels ~30 % narrower, which alone removed most collisions |
| Labels pushed up to 26 px away (T3 on the 120 px map) | displacement capped at `2.4 x fontSize`, along-track nudges preferred, and no ribbon clearance to push against |
| Overlapping strings | hard no-overlap rule; 10 candidate positions per label, then `T<n>`, then drop |
| Long official names (113 px wide) | `short_name` in the schema: 113 -> 60 px widest on Monza |

## 5. Recommendation for slice 02/03

- Schema: `turns[]` with `id, number, name, short_name, apex_s_m, x, y,
  outward, tangent` (validated: finite, inside the outline bbox, `number`
  unique/1-based). Preservation guard for every outline writer.
- Renderer: exactly the pipeline above; constants in one place
  (`FONT_RATIO 0.023`, `FONT_MIN 5`, `FONT_MAX 8`, `GAP_RATIO 0.75`,
  budget `{0, ±1.2, ±2.4} x fontSize`).
- Fallbacks proven by the spike: full label -> nudge -> `T<n>` -> drop; and at
  `mapSize < 150` prefer `T<n>` from the start (TinyPedal's `area_size` floor is
  100 px).
- Port: the only non-pure step is text measurement (`getBBox` here,
  `QFontMetrics` in Qt). Everything else is arithmetic on (apex, outward,
  tangent, fontSize).
