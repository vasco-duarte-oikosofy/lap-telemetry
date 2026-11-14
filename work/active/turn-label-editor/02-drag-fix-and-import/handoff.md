# Handoff — Slice 02: drag fix, import, shipped Imola placement

## Result

| | Before | After |
|---|---|---|
| Vertical drag | inverted (down → label up) | correct |
| Loading a placement | impossible (export only) | **Import JSON…** button + drop a file anywhere |
| Export format | `version: 1` | **`version: 2`** (v1 is accepted and repaired) |
| Imola in the editor | blank layout | **−96° with all 11 names placed** |

## The bug, and why the driver's file needed repair

`draw()` rendered a label at `ay + oy * scale`; `toScreen()` (and the auto-layout
and the drag inverse) all treat sim Y as **up**, using `ay − ry * scale`. So
labels were drawn Y-mirrored while dragging stored correct map-space offsets.
Symptom: down moved the label up, left/right were fine.

That means the offsets in the driver's export are "what looked right *under the
mirrored renderer*". `placementFromPayload()` therefore repairs `version: 1`
payloads by mirroring the **rotated** vector's Y and rotating back:

```js
function repairLegacyOffset(dx, dy, rotation) {
  const [rx, ry] = rotate(dx, dy, rotation);
  return rotate(rx, -ry, -rotation);
}
```

For `rotation = 0` that is just `dy → −dy`; at −96° it is not, which is why the
rotation-aware form matters. Worked example: Imola `t1` exported as
`16.1 / 107.2` becomes `−38.0 / 101.5`, and it then renders exactly where the
driver left it.

## Files

| File | Lines | Role |
|---|---|---|
| `dev/tools/turn-label-editor.html` | 68 | markup + CSS + three `<script src>` tags |
| `dev/tools/turn-label-editor.js` | 313 | state, geometry, auto-layout, drawing, pointer/keyboard, JSON payload |
| `dev/tools/turn-label-editor-ui.js` | 138 | controls, import wiring, copy/download, boot, debug hook |
| `dev/tools/turn-label-data.js` | 4 (184 KB) | **generated** — `window.TURN_LABEL_DATA` + `window.TURN_LABEL_PRESETS` |
| `dev/tools/turn-label-presets.json` | — | human-editable shipped placements (today: Imola) |
| `dev/scripts/build_turn_label_editor.js` | — | regenerates the data file; `--check` guards staleness |
| `dev/scripts/test_turn_label_editor.js` | — | 44 assertions incl. drag directions, import, `file://` smoke |

The 437-line ceiling is what forced the split: the single generated file was
sitting exactly at 437 and could not grow. Each file is now well under it.

## The Imola placement

`dev/tools/turn-label-presets.json` holds the driver's export **verbatim**
(`version: 1`, `display_orientation: -96`, 11 labels), keyed by
`autodromo-enzo-e-dino-ferrari`. The generator inlines it; `presetFor()` converts
it through the same repair path as an import, so it appears for every browser and
machine, not just the one it was made on.

Verified in the browser: 11 labels, **0 overlapping pairs**, none off-canvas,
labels 28–74 px from their corners (screenshot `artifacts/editor-imola.png`).

`Reset this track` on Imola restores this preset. On a track without one it
resets to a blank layout (asserted both ways).

## Verified

- `bash scripts/test-summary.sh --feature turn-label-editor --pw`: **197
  assertions / 6 scripts — ALL PASS**.
- Full `bash scripts/test-summary.sh --pw`: see the commit — must be green.
- `npm run build` succeeds; `dist/compare.html` unchanged.
- The test now also loads the page from a real `file://` URL
  (`pathToFileURL`), so "double-click it" is a tested promise, not an assumption.

## Notes / next

- **Check the Imola placement by eye** and tell me if the repair landed it
  anywhere unexpected — the maths is provable, the aesthetics are yours.
- The exported `lap_length_m` is `0` for Imola because that outline has no
  `lap_length_m` (it predates the field). If a future TinyPedal integration needs
  it, take it from the coaching model for that (track, car) rather than the
  outline.
- Still not wired into TinyPedal: the offsets live only in the editor's export.
  The schema question (`label_offset_m` per turn in the packaged `.turns.json`)
  is unchanged from slice 01's handoff.
- Presets are per-track, not per-(track, layout) — fine while one layout per
  slug, which is how the outlines are named.
