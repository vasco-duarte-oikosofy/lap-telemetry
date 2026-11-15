# Runbook: update TinyPedal map rotation and turn-label placement

Use this for a driver's placement JSON from the
[turn-label editor](../dev/tools/turn-label-editor.html). This updates display
rotation and label positions, **not** the reference lap or coaching model.
Placements are track/layout-wide, not car-specific.

## Ownership and prerequisites

- Work on one confirmed slice; preserve unrelated dirty files in both repos.
- `lap-telemetry/dev/tools/turn-label-presets.json` owns shipped placements.
- `product/data/track-outlines/<slug>.json` owns turn IDs, names and anchors.
- Sibling `../tinypedal/trackmap/<Track Name>.svg` supplies the recorded shape.
- `../tinypedal/tinypedal/data/turn_labels/<Track Name>.turns.json` is generated.
  Never hand-edit it, the generated editor data, or the recorded map to rotate
  the display. Track maps and user settings are normally ignored user data.
- Node dependencies/Playwright and TinyPedal's Qt-enabled `.venv` are needed for
  complete QA. See [setup](SETUP.md) and [testing lessons](TESTING_LESSONS.md).

## 1. Inspect and preserve the input

1. Archive the supplied JSON in the slice's `artifacts/` folder.
2. Check `tool: turn-label-editor`, track slug, layout, `display_orientation`,
   label IDs and finite `dx_m`/`dy_m` values against the outline's turn IDs.
   Do not transfer offsets between layouts or silently drop unknown IDs.
3. Open the editor via `file://`, import the JSON, then inspect **TinyPedal
   preview** at the actual widget size (usually 400 px; also review 600 px).
   Use **Download JSON** after importing legacy files: the editor repairs the
   version-1 Y mirror and negates version < 3 rotation to the widget convention.
   Version 3 uses the widget convention: positive angles rotate clockwise.
   Do not manually flip a version-3 angle or offset.
4. Offsets are metres relative to each turn anchor (sim Y up), independent of
   preview zoom/size. `font_px`, `zoom` and `label_text` are editor settings;
   the exporter ships only offsets and rotation. Live font/name controls stay
   TinyPedal widget settings. Existing curated names are not renamed by import.

## 2. Test first, then store the preset

Add assertions before changing data: compare every input offset and orientation
against the stored preset and exported payload. The existing contract lives in
`dev/scripts/test_shipped_turn_label_placements.js`; browser coverage is in
`dev/scripts/test_turn_label_editor.js`. Add the track to sibling
`tests/test_shipped_placements.py` for real-widget QA.

In `dev/tools/turn-label-presets.json`, add/replace **only** the requested slug:

```json
"circuit-de-barcelona": {
  "version": 3,
  "display_orientation": 0,
  "label_text": "number-name",
  "font_px": 13,
  "zoom": 100,
  "source": "driver placement from the editor",
  "labels": { "t1": { "dx_m": 129.5, "dy_m": 16.1 } }
}
```

This abbreviated example must contain **all** supplied labels in practice.
Preserve the other presets. The input's lap length is informational: do not
copy it into the outline/model; the exporter derives its distance axis from
existing outline data. Changing a reference lap is a separate guarded task.

## 3. Export one track, then rebuild the editor data

From the `lap-telemetry` root (Windows uses `py`; macOS/Linux use `python3`):

```bash
py -X utf8 dev/scripts/export_turn_labels_for_tinypedal.py --track "Circuit de Barcelona"
py -X utf8 dev/scripts/export_turn_labels_for_tinypedal.py --track "Circuit de Barcelona" --check
node dev/scripts/build_turn_label_editor.js
node dev/scripts/build_turn_label_editor.js --check
```

Use the **exact TinyPedal map name**, not the outline slug. Export requires both
an outline with baked turns and a matching SVG. `--trackmap` and `--out` can
select alternate folders. Check for 14 turns in this Barcelona example,
`schema_version: 2`, `display_orientation: 0`, and `label_offset_m` on every
turn. `s_frac`, names and anchors should not change for a placement-only update.
Export **before** rebuilding: the editor generator also embeds TinyPedal maps
and packaged fractions. Avoid an unfiltered export (it can touch other tracks).

## 4. Verify the actual widget, not just the preview

```bash
bash scripts/test-summary.sh dev/scripts/test_shipped_turn_label_placements.js
bash scripts/test-summary.sh dev/scripts/test_tinypedal_turn_label_export.js
npm run build
```

**Run ONLY TinyPedal tests for TinyPedal updates.** Do not run lap-telemetry
feature/full suites, unrelated browser tests or infrastructure guards. This is
an explicit exception to the general testing cadence in AGENTS.md and linked
workflow documents. Build and generated-data freshness checks still apply.

The shipped-placement wrapper runs sibling `tests/test_shipped_placements.py` using
TinyPedal's `.venv/Scripts/python.exe` (Windows) or `.venv/bin/python` (Unix).
If it prints `[SKIP]`, widget verification has **not** happened; supply the
sibling checkout, maps, preset and Qt environment before claiming completion.

Instantiate a widget at each actual size (400 and 600 px), then call
`tests/test_turn_labels_render.py`'s `render_track(...,
use_packaged_orientation=True)`. Assert the real pixmap dimensions, adopted
rotation, label count, zero overlaps, on-canvas bounds, and painted ink. Save
review pixmaps; do not count screenshots alone as assertions. On Windows leave
`QT_QPA_PLATFORM` unset: the offscreen plugin may have no usable font glyphs.

The planner tries supplied offsets first, stretching colliding placements along
their chosen direction before automatic fallback. A screenshot can therefore
look slightly different despite exact packaged offsets. If QA fails, ask for a
re-tuned placement rather than silently changing driver data or planner rules.

For Barcelona, setting `BARCELONA_PLACEMENT_ARTIFACTS` to an absolute directory
when running the shipped-placement wrapper also saves 400/600 px real-widget review images.

## 5. Activate, audit and commit

- Track-map `show_turn_name` must be enabled. For the packaged rotation,
  `use_track_orientation: true` and `display_orientation: 0` are required.
  A nonzero user orientation overrides the package; `use_track_orientation:
  false` disables packaged rotation. Do not overwrite a user's settings without
  approval. Preview/import alone does **not** update the running overlay.
- Restart TinyPedal or reload the track-map widget to discard cached labels and
  orientation. Ask the driver to confirm in-sim label readability and rotation.
- Inspect diffs in **both** repos. Only the requested packaged turn file should
  change; other references/models/outlines/maps/settings must remain untouched.
  Keep `dist/compare.html` current even if the build produces no diff.
- Commit scoped files directly on lap-telemetry `main` and TinyPedal's current
  delivery branch (currently `master`); record both hashes and QA in the slice's
  handoff/learnings and update its PLAN.md row. Push per repository workflow.
  Distinguish automated completion from pending live-driver confirmation.
