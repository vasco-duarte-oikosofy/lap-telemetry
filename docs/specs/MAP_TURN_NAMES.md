# Spec — Turn names on the circuit map

**Status:** proposed (mission [`work/active/map-turn-names`](../work/active/map-turn-names/PLAN.md))

## Goal

The circuit map in `product/dist/compare.html` draws the track shape and the
session lap, but nothing identifies the corners. A driver looking at the map
cannot tell which part of the lap a loss came from, and cannot connect the
coach's corner names ("Becketts", "Curva Grande") to a place on the map.

This feature renders a label at every corner of the map:

```
T1 Abbey
T2 Farm Curve
T3
```

i.e. `T<number> <name>` when the corner has a name, and just `T<number>` when
it does not. Labels are purely visual — no interaction in this mission.

## Where turn names live

Turn names are a property of the **track layout**, not of the car and not of
the session. They therefore belong with the other car-independent, per-layout
artifact: the track outline.

**Decision: the `turns` block lives inside the outline JSON**
(`product/data/track-outlines/<slug>.json`) and is emitted into the generated
static ES module (`product/web/js/static<Track>OutlineData.js`). This is
deliberate:

- The outline and its turn labels share one key (the sim track slug) and one
  layout. Two files would mean two slug maps, two manifest entries and two
  static modules that can silently drift apart.
- Label anchor positions are **derived from the outline geometry** (see
  "Anchor algorithm"), so they must be recomputed whenever the outline changes
  — e.g. a trajectory outline replaced by a TUMFTM one. Keeping them in the
  same file makes that a single, atomic regeneration.
- Curated content in the outline JSON is already precedented
  (`visual_qa.status` / `visual_qa.notes` are hand-edited).

### ⛔ Regeneration guard (required, test-first)

Every script that writes an outline JSON
(`dev/scripts/prepare_all_outlines.js`, `auto_align_outline.js`,
`compute_boundaries.js`, `dev/scripts/register_outline.py`, future ones) must
**preserve an existing `turns` block** instead of overwriting it — the same
"curated models never lose hand-tuned content" rule as bug 24, applied to
outlines. A guard test must fail if any outline writer drops `turns`.

Without this, re-aligning a track would silently delete every curated name.

### Source of names

Names come from the curated coaching models
(`product/data/track-coaching/<track>_<car>.json`), which are the only place
that holds human-verified corner names — with this rule applied at bake time:

- a corner whose `name` matches `/^turn\s*\d+$/i` (the generator's placeholder)
  counts as **unnamed** → label is `T<number>` only;
- `number` is the corner's **ordinal position in the model** (1-based), written
  explicitly into the data. It is never re-derived at render time.

Where several cars have curated models for one track (e.g. Daytona, Laguna
Seca), the bake step must produce one `turns` block; a mismatch in names
between cars is a bake-time error, not a runtime decision.

## Data model

```json
"turns": [
  { "id": "1", "number": 1, "name": "Abbey", "short_name": "Abbey",
    "apex_s_m": 312.0, "x": 412.7, "y": 118.2,
    "outward": [-0.32, 0.95], "tangent": [0.95, 0.32] },
  { "id": "10", "number": 10, "name": "Curva Alboreto (Parabolica)",
    "short_name": "Parabolica", "apex_s_m": 5128.0,
    "x": 218.4, "y": 96.7, "outward": [0.66, -0.75], "tangent": [-0.75, -0.66] },
  { "id": "3", "number": 3, "name": null, "short_name": null,
    "apex_s_m": 782.0, "x": 610.0, "y": 90.0,
    "outward": [0.44, 0.90], "tangent": [-0.90, 0.44] }
]
```

- `id` — the coaching-model corner id, kept for a future interaction slice.
- `number` — 1-based turn number, display order.
- `name` — official/curated name, or `null` when unnamed. Never shortened: the
  coach speaks this string.
- **`short_name`** — optional display-only name for the map, or `null`.
  Official names are far wider than the map can afford
  (`Curva Alboreto (Parabolica)` renders 113 px wide on a 250 px map), so the map
  prefers `short_name`. Curated by hand, never auto-stripped from `name`
  (`Curva Grande` -> `Grande` would be wrong).
- `apex_s_m` — lap distance of the apex, for traceability to the model.
- `x`, `y` — **apex position in sim world coordinates** (same coordinate system
  as `centerline`), baked at generation time so the renderer needs no lap data
  and no per-lap lookup.
- `outward`, `tangent` — unit vectors at the apex (world space): away from the
  track polygon interior, and along the direction of travel. The renderer needs
  them to place, and at most nudge, the text; re-deriving them per frame would
  duplicate the polygon math inside the renderer.

Display text: `T<number> <short_name || name>`, or `T<number>` when both are
null (the generator's `turn N` placeholders count as null).

## Anchor algorithm (bake time)

Per corner, from its `apex_s_m`:

1. Interpolate the world position `P(s)` on a reference lap for the layout at
   `s = apex_s_m` (`sLookup` semantics: linear interpolation between the two
   neighbouring samples of `lap_distance_m`).
2. Compute the local track direction `t` from neighbouring outline centreline
   points, then the outward normal `n` (pointing away from the polygon
   interior — determined by testing both normals against the outline interior,
   not by a fixed sign; the sim's left/right sign convention is not portable,
   see the slice-13 learnings).
3. Bake `x`, `y` = the apex position `P(s)`, plus `outward` = `n` and
   `tangent` = `t` as unit vectors. The pixel gap is applied at **render** time
   (`gap_px / scale`), so baked data stays render-size independent.

   ⚠️ `lap_distance_m` in an exported reference parquet **wraps at the
   start/finish line** (e.g. 2960.68 -> 0.1 -> 2958.72 for a 2961 m lap), so the
   bake must roll the arrays at the single wrap point before interpolating.

The bake script is a `dev/scripts/` tool; it writes the `turns` block, it does
not touch anything else in the JSON.

## Label layout algorithm (render time)

Pure function of `(turns, transform, mapSize)`; only text metrics need a
UI-toolkit call (see "Portability"):

```
layoutTurnLabels(turns, worldToMap, mapSize) -> [{ text, x, y, anchor }]
```

1. Project each apex and its `outward` / `tangent` vectors to map pixels with
   the existing `trackTransform` (`toMapX` / `toMapZ`; `toMapZ` inverts world Y,
   so a screen normal is `(outward.x, -outward.y)`).
2. `fontSize = clamp(mapSize * 0.023, 5, 18)` px — **5.75 px at 250 px**, the size
   validated on the map; `gap_px = fontSize * 0.75`.
3. Text anchor by quadrant: pick `start`/`middle`/`end` and `dominant-baseline`
   so the text grows away from the track, using the sign of the outward normal
   in screen space.
4. **Alternating sides.** Turn 1 goes on the **outside** of the loop, turn 2 on
   the **inside**, turn 3 outside, ... This roughly doubles the room in a dense
   complex (Le Mans has 8 of its 19 turns in sector 3) and, measured on Circuit
   de la Sarthe, it is what makes every label fit: outside-only gave 18/19 with
   one drop, alternating gives **19/19 with names**.
5. **Adjacency budget.** Candidates per label, in this order: the raw spot on
   the preferred side (`apex + side * outward * gap_px`), then nudges of
   `+/-1.2 x fontSize` and `+/-2.4 x fontSize`. Two different caps apply:
   - **along the track** — up to `2.4 x fontSize` (~14 px at 250 px): a label
     sliding beside its corner still reads as attached;
   - **along the normal** — up to `min(2.4 x fontSize, 4 % of mapSize)` (~10 px
     at 250 px, 4.8 px at 120 px): moving away from the track is what makes a
     label look detached.
   A label never ends further than that from its raw spot.
6. **Hard rule: strings never overlap.** In turn order, take the first candidate
   that overlaps no already placed label and stays fully inside the viewBox.
   Candidate order is **text first, then side, then nudge**: keeping the name is
   worth more than keeping the preferred side, and changing side is worth more
   than sliding further from the corner.
7. **Text tiers by map size.** `T<n> <short_name || name>` everywhere; below
   150 px also try `<n> <name>` (dropping the `T` buys ~2 characters on a narrow
   label), and only then `T<n>`. If every candidate fails, drop the label and
   report it.
8. **Crossing the track ribbon is allowed.** There is no clearance requirement
   against the track or its boundaries — labels are read against the shape.
   An earlier revision demanded 2 px of ribbon clearance and pushed labels up to
   26 px away; rejected in review because it detached labels from their corners.
9. Labels are horizontal: no rotation, no text on a path.

Labels render into a dedicated `<g id="track-turn-labels">` group above the
outline and below the zoom arc, with `pointer-events: none`, plus a dot at each
apex and a hairline from the dot to its text.

### Where labels are drawn (implementation note)

The compare app draws its circuit map on **`<canvas id="track-heatmap-canvas">`**
— the SVG twin is hidden ("static outline always prefers canvas") — so the
labels are painted on the canvas too, inside `renderWalkingSkeleton()`, right
after the polylines and the start/finish tick. Consequences that are easy to get
wrong:

- **Measure text with canvas metrics, not `getBBox()`.** The SVG is
  `display: none` in the default path, and `getBBox()` then reports 0×0 for every
  label, which silently empties the map.
- **The viewport is not square** (e.g. 650×514). `mapSize` sizes the text and the
  caps (it is `min(width, height)`), but the bounds check must use the real width
  and height, otherwise every label on the right of the map is rejected.
- **The track name can be `null` on some render paths.** A missing name must
  leave the existing labels alone (skip), never clear them — the cursor-driven
  re-render calls the map without a name.
- Labels are painted with a halo (`strokeText` then `fillText`) so they stay
  readable where they cross the ribbon, which the placement rule allows.

### Type size (slice 05)

The 250 px spike reviewed 5.75 px type, and the first product build froze the
ceiling at that spike's 8 px. On the compare app's map panel (500–950 px wide)
that left **8 px text on a 910 px map** — legible only up close, and the reason
a user said "the font is too small in compare.html". The ceiling is now 18 px,
so the ratio keeps scaling until ~783 px `mapSize`; smaller maps (the whole
TinyPedal range, 100–400 px) are unaffected because the ceiling never binds
there.

The halo width follows the type (`max(1.4, fontSize * 0.16)` px) instead of a
fixed 1.6 px, which read as a hairline once the type grew.

Verified by `dev/scripts/test_turn_labels_scale.js`, which plans **all 14
packaged outlines at three real viewport sizes** (500×454, 650×574, 910×622):
173/173 turns labelled, 0 overlaps, 0 off-map, every named turn keeps its name,
and a 250 px map still produces 5.75 px.

### Measured with this algorithm

Zero string overlaps, every label inside the viewBox, every label beside its
corner (all 14 backfilled tracks, slice 04):

| map size | every turn labelled | notes |
|---|---|---|
| **250 px** (the app) | **14 / 14 tracks** | 8-19 labels each, all with names; label box 2.8-5.1 px from its apex on average, 7 px max |
| 150 px | 13 / 14 | one label degrades to `T<n>` |
| 120 px (TinyPedal's `area_size` floor is 100) | 12 / 14 complete; Le Mans 16/19, Silverstone GP 16/18 | dense sectors number or drop a few labels — 19 labels of ~7 px height do not fit a 120 px square |

## Feature flag

Gated by the existing `#feature-flag-menu` as **`turn names`, ON by default**.
With the flag off the group is empty. A track whose outline has no `turns`
block renders nothing (no error, no placeholder text).

Labels are drawn in every map mode (outline and heatmap) — they are context,
not data.

## Acceptance

Slice by slice; see the mission `PLAN.md`. Feature-level acceptance:

1. With the flag on, Silverstone International shows `T1 Abbey` … `T8 Club` in
   the map, each label within a few px of its apex, no two labels overlapping,
   legible at the canonical 250 px map.
2. Flag off → zero label DOM nodes.
3. A track with no `turns` block renders exactly as it does today.
4. Re-running any outline generator on a track with curated `turns` keeps them
   (guard test).
5. `bash scripts/test-summary.sh --feature map-turn-names` exits 0;
   `npm run build` refreshes `dist/compare.html`.

## Portability — TinyPedal (why the algorithm must be map-size agnostic)

The same labels will be implemented in the sibling repo `../tinypedal`
(`tinypedal/widget/track_map.py`: Qt `QPainter`, configurable `area_size`
with a 100 px minimum, configurable `area_margin`, maps from
`../tinypedal/trackmap/*.svg` which currently contain geometry only, no text).

Therefore:

- the placement math must be a **pure function of (anchors, bbox, map size)** —
  no hard-coded 250, no CSS-dependent measurements;
- font size and gap must **scale with the map**, with a floor for the small
  TinyPedal map (where a 250 px layout would leave labels unreadable);
- every constant (`0.023` font ratio, the 5-8 px clamp range, the 0.75 gap
  ratio, the adjacency budget) and every placement decision is recorded in the
  slice `learnings.md` with the map size it was validated at, so the port does
  not have to rediscover them.

## Non-goals

- Click/hover interaction, click-to-zoom, editing names in the UI.
- Corner highlighting tied to the cursor, delta or coaching facts.
- Label rotation or curved text along the track.
- Deriving names from telemetry (names are curated data, always).
- Curating names for tracks that do not have them yet — that stays a data task
  in the coaching-model pipeline.

## The TinyPedal port (`../tinypedal`)

The same labels are drawn by TinyPedal's Qt track map widget, which is a
different painter, a different coordinate system and a much smaller map
(100–400 px). The layout rule is shared; only the plumbing differs.

### Data: distance, not coordinates

Our corners are in LMU world coordinates. TinyPedal draws its **own** recorded
map polyline (`minfo.mapping.coordinates`), so the two code bases share no
coordinate system — the only common quantity is the distance along the lap.
`dev/scripts/export_turn_labels_for_tinypedal.py` therefore writes, per track:

```json
{ "schema_version": 1, "track_name": "Silverstone International Circuit",
  "lap_length_m": 2934.769,
  "turns": [{ "number": 1, "name": "Abbey", "short_name": null,
              "apex_s_m": 312.0, "s_frac": 0.10631 }] }
```

to `tinypedal/tinypedal/data/turn_labels/<Track Name>.turns.json` (the file name
is the TinyPedal track map name; matching ignores accents, case and punctuation).
The folder must ship inside the package because TinyPedal's `.gitignore` excludes
`/trackmap/` and `*.json`; the data is re-included with a negation line.

### Anchoring by accumulated geometry

At runtime the widget interpolates `s_frac` into the recorded polyline by
**accumulated length**, not by the SVG `dist` values. Those values are not
reliable: several shipped maps store a `dist` polyline that runs backwards
(Silverstone GP: 5865 m down to 5863 m), which collapsed every anchor onto the
first node and produced 2/18 labels. Walking the geometry has no such failure
mode and needs nothing but the polyline.

Normals are derived the same way as in the bake (perpendicular to the tangent,
flipped away from the map centroid), then rotated by `display_orientation`
together with the anchor, so a rotated map keeps its labels attached.

### Type size and halo

`fontSize = min(clamp(mapSize * 0.023 * 1.6, 5, 18), widget font_size)` — the map
decides, the user's widget font is only an upper bound. The `1.6` is the one
presentation constant that differs from the compare app: the widget's map is
100–400 px against the app's 500–950 px, and the same ratio gave 7 px type, which
is too small to read on an overlay. At the default `area_size` 400 /
`area_margin` 40 with the default `font_size` 15 that is **11.8 px**.

The cost of the larger type is measurable and accepted: at 400 px, **170/173**
corners still get a label and **126/136** named corners keep their name (three
crowded corners on Silverstone GP and Paul Ricard 1A-V2 drop their label, because
overlapping is a hard rule). At `area_size` 600 the widget font cap of 15 px
applies instead and **173/173** corners and 133/136 names fit again.

The halo pen is centred on the glyph outline, so it competes with the stems; Qt
hint-rounds stems to about 1 px, which is why the compare app's 0.16 em halo is
fine at its 13 px but blurs these labels. Measured on the real Monza labels:

| halo | ink growth at 7.4 px | at 11.8 px |
|---|---|---|
| 0.16 em | +49 % | +86 % |
| 0.08 em | +30 % | +29 % |
| 0.06 em | +22 % | **+22 %** |

0.06 em at every size, and a test fails above 25 % inflation.

### Options

| Option | Default | Meaning |
|---|---|---|
| `show_turn_name` | `True` | draw the labels |
| `turn_name_color` | `#CCCCCC` | text colour |
| `turn_name_outline_color` | `#88000000` | halo (alpha `00` disables it) |

### Tests (all headless, `QT_QPA_PLATFORM=offscreen`)

| Script | What it proves |
|---|---|
| `tests/test_turn_labels.py` | the layout rule on synthetic tracks: tiers, alternating sides, both caps, no overlap, degradation, anchoring, loading |
| `tests/test_turn_labels_render.py` | every shipped track: **173/173 corners labelled**, 0 overlaps, nothing off the canvas, **136/136 named corners keep their name**, rotation-safe |
| `tests/test_track_map_widget_labels.py` | the real widget class draws the labels: option on by default, one label per corner, fewer pixels when off, graceful without data |

Cross-language parity is enforced from **this** repo: `dev/scripts/test_turn_labels_parity.js`
feeds identical anchors and identical text metrics to the JS and Python planners
and requires identical text, side and geometry (currently 0.0 px difference
across four map sizes, including a 100 px map).
