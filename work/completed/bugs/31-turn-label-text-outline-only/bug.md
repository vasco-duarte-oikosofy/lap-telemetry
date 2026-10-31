# Bug 31 — Turn labels on the TinyPedal track map render as an outline, not solid text

## Symptom

On the live overlay the turn labels read as hollow outlines: you can see the
glyph edges but the letters have no body. Reported as "the text is just the
outline. Fill it, and make it white."

## Cause (measured)

Two independent things, both in `tinypedal/widget/track_map.py`:

1. **The halo pen was stroking the text path itself.** `QPainter` pens are
   centred on the path, so a 0.71 px pen on 11.8 px type paints ±0.35 px across
   every glyph outline. Consolas' stems are ~1 px at that size, so the pen covered
   most of each stem and the fill that followed was left antialiased and grey —
   which is exactly what "just the outline" looks like.

2. **A plain fill is not solid at 11.8 px anyway.** Measured on the real Monza
   labels, only **33 %** of the pixels strictly inside the glyphs reached opaque
   white; the rest are antialiased partial coverage. The text needs a self-stroke
   in its own colour to look filled.

3. The colour was `#CCCCCC` (light grey), and because Qt only *adds* missing keys
   to an existing preset, installs that had already run the patched build kept
   grey even after the default changed to white.

## Fix

- Halo is now an **outside-only ring**: `QPainterPathStroker` around the glyph,
  subtracting the *thickened* glyph (`path.united(stroker.createStroke(path))` —
  subtracting the raw path is not enough, because the stroke band also extends
  inward and covers a 1 px stem). The ring is painted **after** the text, so it
  can only touch pixels the letters do not cover.
- The glyph is filled **and** stroked in `turn_name_color` (`TURN_SOLIDIFY_EM`
  0.085 → 1.0 px at 11.8 px). Interior opaque-white coverage: **33 % → 100 %**
  (measured: 1928/1928 interior pixels opaque white, worst alpha 239, worst red 247).
- The layout reserves the self-stroke width in `measure()`, so the no-overlap rule
  still holds (0 overlaps on all 14 tracks).
- `turn_name_color` default is now `#FFFFFF`. **Existing presets keep the old
  `#CCCCCC`; set it to `#FFFFFF` (or delete the key) to get white labels.**

## Guards added

`tests/test_track_map_widget_labels.py` now asserts:

- every pixel strictly inside a glyph is opaque and white (worst alpha 239,
  worst red 247) — a plain fill fails this at 33 %;
- the halo ring is drawn, and only outside the letters (dark pixels around the
  labels appear with the halo on, none with it off).

`tests/test_turn_labels_render.py` no longer re-implements the painter: it renders
through the real widget, so review images cannot drift from the app again.

## Status

✅ Fixed in `63296a10` (TinyPedal) + `6603a22` (docs here). Confirmed live by the
user — "tinypedal map is fine now" — and moved to `work/completed/bugs/`.

Verification on the shipped data: all 173 corners of the 14 packaged tracks are
labelled, 0 overlaps, and every glyph interior pixel is opaque white (1928/1928
on Monza, worst alpha 239, worst red 247).
