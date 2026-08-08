# Bug 26: Track outlines are not visible in the compare.html viewer

## Observed

The static track outline (the faint grey boundary + dashed centerline drawn
around the circuit map) does not appear in the `compare.html` viewer, even for
tracks that have a registered outline (e.g. Daytona, Laguna Seca, Spa, etc.).

**Key clue:** the outline **IS visible for Monza**, but not for the others.
This proves the rendering pipeline works, so the issue is specific to certain
outlines (likely the newly added trajectory outlines vs. the Monza TUMFTM
outline).

**Tracks confirmed NOT working** (user-tested): Spa, Sebring, Le Mans,
Sao Paulo, Silverstone, Fuji — plus Daytona and Laguna Seca. So it is **not**
just the trajectory outlines: Spa, Silverstone and Sao Paulo are TUMFTM real
outlines and they also fail. Only **Monza** renders.

## What has been verified as WORKING (so far)

Investigation ruled out the obvious causes:

- **Outline JSON is valid** — `register_outline.py` validates it: `✅ Outline JSON is valid`.
- **Static ES module exists and exports correctly** — `staticDaytonaInternationalSpeedwayRoadCourseOutlineData.js` (73 KB) exports the outline object.
- **Manifest has the entry** — `trackOutlineManifest.js` has the import and the `OUTLINES` map entry for the track slug.
- **Lookup works** — `findOutlineByTrackName('Daytona International Speedway Road Course')` returns the outline (slug matches the manifest key).
- **Rendering works** — `renderStaticTrackOutlineSvg()` produces a non-empty SVG with `static-track-centerline` and `static-track-boundary` polylines.
- **Bundle contains the data** — `product/dist/compare.html` contains the outline data (8× "Single lap trajectory").
- **Coordinates match session data** — outline centerline range `x[-319,883] y[-1035,386]` equals the session `pos_x`/`pos_z` range, so the transform should place it on-screen.

## Suspected areas (not yet confirmed)

- **CSS visibility** — `.static-track-boundary` uses `stroke: rgba(210,210,210,0.28)` and `.static-track-centerline` uses `rgba(210,210,210,0.18)`. These are extremely faint; the outline may be drawn but effectively invisible against the dark map background. Compare against how the outline is expected to look.
- **Map mode / layering** — the static outline is rendered into `#static-track-outline` regardless of mode, but it may be hidden or covered by the heatmap/segment layers in some modes.
- **Stale bundle** — the user may be running a cached/older `compare.html`; confirm a fresh `npm run build` + hard reload shows it.
- **Transform mismatch** — `renderStaticTrackOutlineSvg` uses `trackTransform.toMapX/toMapZ`; if the transform is built from a different coordinate basis than the outline, the outline could be scaled off-screen.

## Repro

1. `npm run build`
2. Open `product/dist/compare.html` via `file://`
3. Load a session for a track that has an outline (e.g. Daytona, Laguna Seca, Spa)
4. Observe the circuit map — the static outline is not visible

## Files

- `product/web/js/trackOutlineManifest.js` — manifest + `findOutlineByTrackName`
- `product/web/js/staticTrackOutline.js` — `renderStaticTrackOutlineSvg` / `drawStaticTrackOutline`
- `product/web/js/circuitMap.js` — calls `findOutlineByTrackName` + `renderStaticTrackOutlineSvg`
- `product/web/js/trackHeatmapMap.js` — calls `findOutlineByTrackName` + `drawStaticTrackOutline`
- `product/web/css/styles.css` — `.static-track-boundary` / `.static-track-centerline` styles

## Status

🐛 Open — root cause not yet determined.
