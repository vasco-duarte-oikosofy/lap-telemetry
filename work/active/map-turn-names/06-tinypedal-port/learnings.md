# Learnings — Slice 06 (TinyPedal port)

- **The two apps share no coordinate system, only lap distance.** Our corners are
  LMU world coordinates; TinyPedal draws its own recorded
  `(position_longitudinal, position_lateral)` polyline. Anything geometric would
  have needed an alignment step. `s_frac` (fraction of the lap, 0 at the
  start/finish line) is the one quantity both sides agree on, and it is also what
  makes the data tiny (5 numbers per corner).

- **The SVG `dist` polyline cannot be trusted — but not for the reason I assumed.**
  I first interpolated anchors into `dist`, the (lap distance, elevation) pairs
  recorded with the map. Some shipped maps store a `dist` polyline that runs
  *backwards* (Silverstone GP: 5865 m → 5863 m), so every corner clamped onto
  node 0: all anchors identical, 2/18 labels drawn, no error anywhere. Walking the
  polyline's own accumulated length removed the failure mode entirely and let the
  widget drop its dependency on `minfo.mapping.elevations`.

- **TinyPedal's `.gitignore` is aggressive: `/trackmap/`, `*.json`, `test*.py`.**
  Shipping per-track JSON inside the user data folder would never have been
  committed. The data now lives in `tinypedal/data/turn_labels/`, and *both* the
  data and the tests need negation lines — and those negations must come **after**
  the rules they override, otherwise git silently keeps ignoring the files (the
  first attempt put them before `*.json` and nothing was staged).

- **`minfo.mapping.elevations` is the dists field.** The module assigns
  `output.elevations = recorder.output.dists`, so a "lap distance" column hides
  under an elevation name. Moot now, but worth knowing before trusting the model.

- **A widget can be tested headless without the app or a sim.** Building the real
  `Realtime` widget needs a loaded preset (`cfg.load_global()` then
  `cfg.load_user()`), because importing `tinypedal.widget` pulls in
  `api_control`, which reads `cfg.telemetry`. Once that is done the widget paints
  into its pixmap offscreen and the painted-pixel count proves the labels are on
  the canvas (2246 samples with labels vs 1577 without).

- **Qt requires integer pixel sizes** (`QFont.setPixelSize`), while the ratio
  gives 7.36 px. Painting with `round(size)` and measuring with the same
  `QFontMetricsF` keeps the layout self-consistent; only the gap differs by a
  fraction of a pixel.

- **Cross-language duplication needs a parity test, not discipline.** The planner
  now exists twice. `dev/scripts/test_turn_labels_parity.js` runs both on
  identical anchors and identical text metrics and compares text, side and
  geometry to 1e-9 across four map sizes (including a 100 px map). Any future
  change to one side fails immediately.

- **A layout rule measured in font sizes ports for free.** Because every cap and
  gap is expressed in font sizes, the same constants produce the same relative
  result at 400 px as at 950 px — the port needed no re-tuning, and 173/173
  corners are labelled on the first attempt once the anchors were right.

- **The first review images were tofu boxes and I shipped them anyway.** On
  Windows the `offscreen` Qt platform has an **empty font database** (0 families),
  so every glyph renders as a hollow square — and `QFontMetricsF` still returns
  plausible advances, so nothing looks broken in code. The measurements were even
  *wrong* because of it (tofu boxes are wider than Consolas: 133/136 names instead
  of the real 136/136). Qt's **default** platform (`windows`) renders into a
  QImage with no window at all and has 241 families; `offscreen` is only needed on
  a headless box, where fontconfig supplies fonts. Both render tests now assert
  `QFontDatabase().families()` and `QFontMetricsF.inFont("A")` before drawing.

- **The saved images then had no labels at all — and my test didn't notice.**
  `draw_turn_names()` reads the coordinates, and those were kept in
  `self.turn_coords`, which only `update_map()` refreshed. A save path that called
  `create_map_path()`/`draw_map_image()` directly inherited stale/empty coordinates,
  `anchor_turns()` raised, and a `except ValueError: return` swallowed it: a clean
  canvas, no error, PASS. Fixed by making `create_map_path()` store `self.map_coords`
  — the coordinates the current map frame was built from — so the labels can never
  be stale relative to `map_range`/`scale`/`offset`. The test now counts painted
  pixels *inside the label boxes of the saved file*.

- **`widget.pixmap_map` is one object reused for every render.** Saving a reference
  to it and saving later gave me a "0 degrees" file that was actually the 90 degree
  render. Every save needs `.copy()`.

- **A proportional halo is wrong for small type.** The pen is centred on the glyph
  outline, and Qt hint-rounds stems to ~1 px below 10 px, so the compare app's
  0.16 em halo — fine at its 13 px — fattens 7 px labels by **+49 % ink** and the
  letters blur into blobs. Measured on the real Monza labels: 0.16 em +49 %,
  0.08 em +30 %, 0.05 em +20 %. Below 10 px the halo is now 0.05 em, above it keeps
  0.16 em, and a test fails if the inflation exceeds 25 %.

- **My own ASCII dumps lied to me twice.** 7 px antialiased text on a transparent
  pixmap has alpha 30–120, so a `luminance = colour x alpha` ramp shows it as
  nearly blank. Count pixels by alpha instead of eyeballing a ramp; that is what
  finally distinguished "no labels in the file" from "labels too faint for my dump".

- **60 % larger type is not free, and the price is worth measuring before the
  user asks.** Growing the widget's type from 7.4 to 11.8 px keeps 170/173
  corners labelled and 126/136 names at the default 400 px map (three crowded
  corners on Silverstone GP and Paul Ricard 1A-V2 lose their label, because
  overlapping is a hard rule). Nothing else regressed. The escape hatch is
  `area_size`: at 600 px the widget font cap of 15 px kicks in and everything
  fits again (173/173, 133/136). Both numbers are now asserted in
  `tests/test_turn_labels_render.py`, so a future change to the ratio cannot
  quietly cost more.

- **A larger font made the halo worse, not better.** At 11.8 px the 0.16 em halo
  cost **+86 % ink** (it was +49 % at 7.4 px). The sweep at the new size
  (0.04 em +15 %, 0.06 em +22 %, 0.08 em +29 %, 0.10 em +46 %) pointed at a single
  0.06 em rule for every size, which also removed the two-branch special case.

- **The widget's font cap accidentally protects coverage.** The render test
  measured type without it and lost two more labels (19.1 px type at a 520 px
  map) than the widget actually draws (15 px). Tests that mirror the widget must
  mirror its caps too.

- **Parity caught the divergence the moment it appeared.** With the widget's
  `font_scale` at 1.6, the JS and Python plans differed by 17 px of geometry —
  and the test still said PASS, because it compared text and side but never
  asserted the geometry delta. It now feeds an explicit identical config to both
  planners (the rule is shared; the presentation constants are not) and fails on
  any delta above 1e-9.
