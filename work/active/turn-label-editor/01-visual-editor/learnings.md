# Learnings — Slice 01 (visual turn-label editor)

- **A `file://` page cannot `fetch()` the outlines**, and inlining all 30 raw
  files would be 14 MB. Inlining only what the editor draws — slug, names,
  `lap_length_m`, the 500-point centreline and the turn anchors, rounded to
  0.1 m — is 203 KB for 19 layouts. The boundaries (2×500 points per track) are
  ~80 % of the file size and the label editor never uses them.

- **Only 19 of the 28 outline files have baked turns.** The other nine (Monza
  base, Spa, COTA, Bahrain base/outer, Lusail, Algarve, Barcelona-median, one
  Fuji variant) are centreline-only, so there is nothing to place — and those
  are exactly the nine tracks with no packaged `.turns.json` in the sibling
  repo. The generator reports them as "have no turns" instead of failing.

- **`tangent` was missing from the first payload and it quietly broke the
  layout.** With only `outward`, every candidate for a label sits on one line
  through the corner, so the along-track fan does nothing and dense tracks piled
  up (Paul Ricard 1A-V2-Short: 4/13 names clear). Copying `turn.tangent` (present
  in every outline) took it to 8/13. Deriving a fallback tangent from the normal
  (`[-oy, ox]`) costs one line and keeps an odd outline usable.

- **Off-canvas is a collision.** The first fan happily parked `Camp` at
  x = −25 px: invisible, and no state check would notice. Treating
  "outside the canvas" as a hit fixed both visibility and several overlaps.

- **Rotation must not re-shuffle the auto layout.** Two separate causes:
  1. the fit scale changes with rotation (the rotated bounding box changes), so
     a *pixel* offset is not stable — offsets must be map-space metres;
  2. the auto placement itself was computed with the rotated bounding box, so
     turning the map re-ran the fan and moved labels.
  Fix: compute the fan against an **unrotated** view and cache it per
  (track, text mode, font, zoom, canvas size). Labels then rotate with the map
  as a rigid body, which is what "attached to the corner" should mean.

- **The generated file hit the 437-line ceiling three times.** The template is
  the source of truth and the ceiling applies to the *output*; freeing lines by
  collapsing one-liners (`labelText`, `setting`/`outline`, the two checkbox
  listeners) is cheap and does not hurt readability. Watch it every time you add
  a block — the generator fails the build when it overflows, so it cannot slip
  through.

- **Playwright + `localStorage`:** serve the tool over the repo's tiny test
  server (`dev/scripts/lib/test-server.js`) rather than `file://` — Chromium
  treats a `file://` page as an opaque origin in some configurations, so
  persistence tests would pass or fail by accident. Double-clicking the real file
  still works; the `try/catch` around `localStorage` covers the browsers where it
  does not.

- **Expose a debug hook** (`window.__turnLabelEditor`) rather than scraping the
  canvas. It made the drag/rotation/persistence assertions four lines each, and
  it is the simplest way for a human to inspect what the editor believes too.

- **`display_orientation` is not an invention**: TinyPedal's track-map widget
  already reads `wcfg["display_orientation"]` as an integer degree count and
  rotates the map with `calc.scale_map(..., angle)`, so the slider's value can be
  used verbatim there. The missing half is the label offset — the widget plans
  its own label positions at run time, so the editor's offsets need a schema
  change in the sibling repo before they can ship.
