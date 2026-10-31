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
