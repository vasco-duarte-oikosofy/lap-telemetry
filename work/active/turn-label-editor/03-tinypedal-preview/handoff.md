# Handoff — Slice 03: TinyPedal preview tab

## What the tab does

`TinyPedal preview` draws what the live overlay will draw, from the widget's own
code paths (ported to canvas, see `dev/tools/turn-label-editor-preview.js`):

| Widget behaviour | Ported as |
|---|---|
| map shape | TinyPedal's recorded `trackmap/<track>.svg` polyline (18 of 19 tracks; Silverstone GP-ELMS has no SVG and falls back, and says so) |
| rotation | `rotate_coordinate` in its y-down frame (`display_orientation`) |
| fit | `calc.scale_map`: square area, 40 px margin, shorter axis centred |
| corner anchors | `anchor_from_fraction` by `s_frac` on the recorded polyline + outward normal from the centroid |
| type size | `min(font_size(area − 2·margin), max(editor font, 5))` |
| placement | `plan_turn_labels`: odd turns outside / even inside, text degrades `T1 Name → 1 Name → T1`, never overlaps, drops when nothing fits |
| start/finish | a tick across the track at the first recorded point (the widget's own line is config-driven; close enough to judge rotation) |

Widget size is selectable (250/400/600/800 px); the status line reports the map
source, margin, font, rotation, how many labels were placed/dropped and how many
came from **your** placement versus TinyPedal's own rule.

## The real finding: the two tabs rotated the wrong way relative to each other

The editor rotated the map counter-clockwise for a positive angle; TinyPedal's
`rotate_coordinate` (y-down) is clockwise. Measured on Copse→Brooklands:

| angle | editor screen bearing | TinyPedal screen bearing |
|---:|---:|---:|
| 0° | +158.24° | +158.24° |
| +30° | +128.24° | −171.76° (≡ +188.24°) |

So the editor's convention was exactly TinyPedal's **negated**. Two consequences:

1. **The editor now uses TinyPedal's convention** (`toDisplay()` negates Y, then
   rotates in the y-down frame). `display_orientation` is therefore the number the
   widget takes, with no mental arithmetic.
2. **Existing placement files are migrated**: `version < 3` has its rotation
   negated on import. The driver's Imola file (`version: 1`, `-96`) now loads as
   **+96** and looks exactly as approved — the offsets are rotation-independent,
   so only the angle changed. Export is `version: 3`.

The test pins this: every Imola label must sit the same way round its corner in
both tabs (worst error < 25° across 11 corners, measured 2026‑11‑14).

## Files

| File | Lines | Change |
|---|---|---|
| `dev/tools/turn-label-editor-preview.js` | 248 | **new** — the widget port + preview drawing |
| `dev/tools/turn-label-editor.js` | 331 | display-space transform (TinyPedal convention), `version: 3`, v1/v2 migration |
| `dev/tools/turn-label-editor-ui.js` | 154 | tab state (`view.tab`, `setTab`, `render`) so every control redraws the active tab |
| `dev/tools/turn-label-editor.html` | 94 | tab bar + preview controls |
| `dev/tools/turn-label-data.js` | 321 KB | inlines each track's TinyPedal polyline + packaged `s_frac` values |
| `dev/scripts/build_turn_label_editor.js` | — | reads `../tinypedal/trackmap/*.svg` and `.../turn_labels/*.turns.json`, resolves the map name via `track_name_mapping.canonical_lmu_track_name` when needed |
| `dev/scripts/test_turn_label_editor.js` | — | preview assertions incl. the cross-tab agreement check |

Screenshots: `artifacts/preview-imola-600.png`, `artifacts/preview-la-sarthe-600.png`.

## Verified

- `--feature turn-label-editor --pw`: **204 assertions / 6 scripts — ALL PASS**.
- Full `--pw` suite: **2915 assertions / 99 scripts — ALL PASS**.
- `npm run build` succeeds; `dist/compare.html` unchanged.
- `file://` smoke still passes (four classic scripts, relative paths).

## Deferred / honest limits

- **Qt vs canvas text metrics** differ by a pixel here and there, so a label that
  the widget *just* fits may show as dropped. The preview is a judge, not an
  oracle.
- The widget's start/finish line is config-driven (`start_line_length`, sector
  lines); the preview draws a simple tick.
- The preview does not render sector lines, in-pit markers, or the widget's own
  colours/transparency settings.
- **Still not wired into TinyPedal**: the placement offsets live only in the
  editor's export/presets. The next step is unchanged — add an optional
  `label_offset_m` (and optionally `display_orientation`) to the packaged
  `.turns.json` and make `plan_turn_labels` honour it before its own fan.
- Imola's outline has no `lap_length_m`, so the exported field is 0; the *preview*
  handles it (it divides by the TinyPedal polyline length instead).
