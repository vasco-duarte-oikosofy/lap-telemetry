# Learnings — Slice 03 (rendering the labels)

- **The product's circuit map is a canvas, not the SVG.** `trackHeatmapController`
  sets `svg.style.display = 'none'` with the comment "static outline always
  prefers canvas", and draws everything in `renderWalkingSkeleton()`. An SVG
  `<g id="track-turn-labels">` group renders into a hidden element and looks
  exactly like "the feature does nothing". The spec said "SVG group"; the spec
  was wrong and is now corrected.

- **`getBBox()` returns 0×0 when the SVG is `display:none`.** The first canvas
  version still measured text through a hidden `<text>` probe, so every label
  had zero size and every plan came back empty — with no error anywhere. Canvas
  `measureText` has no layout dependency and is the right tool (and mirrors
  `QFontMetrics` for the Qt port).

- **The map viewport is rectangular.** A single `mapSize` (650×514 → 514) was
  applied to both axes of the bounds check, so every label in the right-hand
  136 px of the map was rejected as "outside the viewBox" and all 14 Barcelona
  labels were dropped. `mapSize` now only sizes text and caps; bounds use
  `mapWidth`/`mapHeight`.

- **A missing track name must not clear the labels.** `cursor.js` re-renders the
  map without `trackName`; clearing on null made labels flash away on the first
  mouse move. Null name = skip, flag off = clear.

- **The dev session fixtures have no real geometry.** Every Barcelona/Spass
  fixture in `dev/sessions/` stores a constant `pos_x_m/pos_z_m` (e.g. x =
  106.4 for the whole file), which makes `fitToView` compute a scale of ~480
  instead of ~0.32 and puts the track off-screen. The label code was blamed for
  a "broken map" that was actually an unusable fixture. Fix: a committed 2-lap
  fixture sliced from a real session
  (`session_20261031T051245Z_silverstone-international-circuit_lmu_quali_2laps.parquet`).

- **Fixture file names carry the track name.** `inferTrackNameFromFileName()`
  only matches `_<8-date>T<6-time>Z_<track>_lmu…`, so a fixture named
  `session_fixture_…` yields `trackName === null` and silently no labels. The
  fixture keeps the real session's naming convention.

- **`__setFeatureFlag()` flips state only.** Nothing re-renders, so a test that
  toggles the flag sees stale labels. Force a render (the ResizeObserver path)
  before asserting.

- **Testing the planner without a browser paid off.** Because text metrics are
  injected, the pure planner is covered by 12 fast assertions (alternating
  sides, both nudge caps, text tiers, degradation, determinism) and the browser
  test only has to prove the wiring and the pixels.
