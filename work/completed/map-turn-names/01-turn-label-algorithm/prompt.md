# Slice 01 — Turn label placement algorithm (offline spike)

**Type:** throwaway spike (AGENTS.md "spike, then stabilize"). **No product
code, no tests, no commits to `product/`.** The output is a picture and a
written algorithm; both get thrown away once slice 02/03 implement it for real.

**Spec:** [`docs/specs/MAP_TURN_NAMES.md`](../../../docs/specs/MAP_TURN_NAMES.md)

## Goal

Prove, on real data, that we can place `T1 Abbey`-style labels on the track map
so they are (a) legible, (b) outside the track ribbon, (c) not colliding, at the
canonical **250 px** map **and** at a **~120 px** map (the TinyPedal constraint).
Then hand the picture to the user for approval.

## Inputs

| Input | Path |
|---|---|
| Outline + geometry | `product/data/track-outlines/silverstone-international-circuit.json` — *does not exist yet* (slice 30 of the track-outline mission is not done); use `autodromo-nazionale-monza.json` and, for a second, denser track, `michelin-raceway-road-atlanta.json` |
| Reference laps | `product/data/reference-laps/michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.16.304.parquet`, `.../monza-curva-grande-circuit_..._time_01.35.182.parquet` |
| Corner names | `product/data/track-coaching/<track>_<car>.json` |

Pick **two** tracks with curated names and different corner density, e.g. Road
Atlanta (12 corners) and Monza Curva Grande (10 corners). If a track has an
outline but no curated names, skip it — the spike is about placement, not data.

## Steps

1. **Bake anchors.** For each corner `apex_s_m`, interpolate the world position
   on the reference lap (`lap_distance_m` → `pos_x_m` / `pos_z_m`, linear
   between neighbours). Record it next to the corner name and ordinal number.
2. **Outward normal.** At each anchor take the local centreline direction, then
   choose the normal pointing **away from the polygon interior** (ray-cast test
   against the outline centreline — do not assume a left/right sign).
3. **Offset.** Offset the anchor by `gap_px * world_per_px` along that normal,
   with `world_per_px = bbox_diagonal / map_size` for the map size under test.
4. **Text placement.** Text = `T<n> <name>`, or `T<n>` when the model name
   matches `/^turn\s*\d+$/i`. Choose `text-anchor` / baseline from the screen
   quadrant of the normal so the string grows away from the track.
5. **Sizes.** `fontSize = clamp(map_size * 0.033, 6, 11)`; render each track at
   **250 px** and at **120 px**, plus a 250 px render with the font floor
   disabled, so we can see where legibility actually breaks.
6. **Overlap measurement.** Compute label bounding boxes (approximate: width =
   `0.55 * fontSize * len(text)`) and report every intersecting pair — do **not**
   suppress them yet. We want the number that decides whether slice 05
   (declutter) is needed at all.
7. **Render** one PNG per (track, size) with Playwright (headless Chromium is
   already a devDependency; the existing outline tests show the pattern), with
   the track ribbon drawn under the labels so we can see clearance.

## Deliverables (in `artifacts/`)

- `anchors-<track>.json` — baked anchors (the prototype of the `turns` block).
- `labels-<track>-250.png`, `labels-<track>-120.png`,
  `labels-<track>-250-nofontfloor.png`.
- `ALGORITHM.md` — the exact steps above, with every constant used and the
  measured overlap counts per size, written so it can be ported to
  `../tinypedal` (Qt/QPainter, `area_size` min 100 px, `area_margin`).
- A one-line recommendation: is declutter needed at 250 px? At 120 px? What is
  the smallest map size where `T<n> <name>` is still worth showing, and what
  should degrade first (drop names → keep numbers)?

## Non-goals

- No changes to `product/web/`, no feature flag, no manifest/static module.
- No `turns` block written into any `product/data/track-outlines/*.json`
  (that is slice 02, with its regeneration guard).
- No click/hover behaviour, no rotation, no per-car variants.

## Acceptance

The user looks at the images and approves the placement rule — or sends it back
with what to change. Nothing is merged from this slice; only `work/…`
artifacts are committed.

## Notes for the port

Whatever we learn about font size, gap, and declutter must be recorded in
`learnings.md` with the map size it was validated at. TinyPedal draws with
QPainter into a configurable `area_size` (100 px minimum) with a configurable
margin, from its own `trackmap/*.svg` geometry — so anything that assumes a
250 px viewBox or measures text with the DOM will not port.
