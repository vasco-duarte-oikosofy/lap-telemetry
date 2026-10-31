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
  { "id": "1", "number": 1, "name": "Abbey",      "apex_s_m": 312.0, "x": 412.7, "y": 118.2 },
  { "id": "2", "number": 2, "name": "Farm Curve", "apex_s_m": 542.7, "x": 505.1, "y": 63.4 },
  { "id": "3", "number": 3, "name": null,         "apex_s_m": 782.0, "x": 610.0, "y": 90.0 }
]
```

- `id` — the coaching-model corner id, kept for a future interaction slice.
- `number` — 1-based turn number, display order.
- `name` — official/curated name, or `null` when unnamed.
- `apex_s_m` — lap distance of the apex, for traceability to the model.
- `x`, `y` — **label anchor in sim world coordinates** (the same coordinate
  system as `centerline`), baked at generation time so the renderer needs no
  lap data and no per-lap lookup.

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
3. Offset the anchor along `n` by a **world-space distance equivalent to a
   fixed pixel gap** at the canonical map size, so labels clear the track
   ribbon at any map size:

   `offset_world = gap_px * world_per_px`, where `world_per_px` is derived from
   the outline bounding box and the canonical 250 px viewBox.

The bake script is a `dev/scripts/` tool; it writes the `turns` block, it does
not touch anything else in the JSON.

## Label layout algorithm (render time)

Pure function, no DOM access, so it can be ported (see "Portability"):

```
layoutTurnLabels(turns, worldToMap, mapSize) -> [{ text, x, y, anchor }]
```

1. Project each anchor to map pixels with the existing `trackTransform`
   (`toMapX` / `toMapZ`) — the same transform the outline uses.
2. `fontSize = clamp(mapSize * 0.033, 6, 11)` px; `gap_px = fontSize * 0.9`.
3. Text anchor by quadrant: pick `start`/`middle`/`end` and `dominant-baseline`
   so the text grows away from the track, using the sign of the outward normal
   in screen space.
4. Declutter (only if the spike shows real overlap): greedy suppression in
   turn order — a label whose estimated rect intersects an already-placed rect
   is dropped, so the lower turn number always wins. No label rotation in
   scope.

Labels render into a dedicated `<g id="track-turn-labels">` group above the
outline and below the zoom arc, with `pointer-events: none`.

## Feature flag

Gated by the existing `#feature-flag-menu` as **`turn names`, ON by default**.
With the flag off the group is empty. A track whose outline has no `turns`
block renders nothing (no error, no placeholder text).

Labels are drawn in every map mode (outline and heatmap) — they are context,
not data.

## Acceptance

Slice by slice; see the mission `PLAN.md`. Feature-level acceptance:

1. With the flag on, Silverstone International shows `T1 Abbey` … `T8 Club` in
   the map, positioned outside the track ribbon, legible at the canonical
   250 px map and not overlapping the track line.
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
