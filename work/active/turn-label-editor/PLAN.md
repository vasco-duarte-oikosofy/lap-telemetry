# Mission: Turn Label Editor

**Goal:** Place TinyPedal's corner-name labels by eye, on any track, and choose
the map rotation that fits the LMU screen — instead of guessing numbers in the
label JSON and re-running `export_turn_labels_for_tinypedal.py` to see the
result.

**Why now.** The Paul Ricard ELMS refresh (slice 54) showed the cost of working
blind: a 22 m apex change silently pushed a label into its neighbour and only the
TinyPedal widget test noticed. Placement is a *visual* decision — it needs a
canvas, a drag handle and a rotation slider, not a diff.

**Where it lives:** `dev/tools/turn-label-editor.html` — a standalone dev tool
(generated, single file, opens via `file://` like `dist/compare.html`).

**Feature tests:** `bash scripts/test-summary.sh --feature turn-label-editor`

---

## Vertical slices

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-visual-editor` | ✅ `6358258` | `dev/tools/turn-label-editor.html` — single file, opens via `file://`, 19 tracks with baked turns, per-label drag + arrow nudge, `-180…+180°` rotation slider (= TinyPedal `display_orientation`), zoom/font/text mode, localStorage persistence, JSON copy/download. Generated from a template + the outlines (`--check` guards staleness); Playwright test drives the real page |
| `02-drag-fix-and-import` | ✅ `67053fc` | Vertical drag was inverted (labels were drawn Y-mirrored while offsets were stored correctly) — fixed and direction-pinned in the test. Placement files can now be **imported** (button or drag-drop), export format is `version: 2`, and `version: 1` files are repaired with a rotation-aware Y mirror. The driver's Imola placement (‑96°, 11 labels) ships in `dev/tools/turn-label-presets.json` and is what Imola opens with; Reset restores presets. Tool split into app + ui + generated data (the old single file was exactly at the 437-line ceiling), with a real `file://` smoke test |
| `03-tinypedal-preview` | ✅ `6decc35` | **TinyPedal preview tab**: renders the widget's own recorded map SVG, `display_orientation` rotation, `scale_map` fit/margin, `font_size` rule and `plan_turn_labels` placement, with the editor's placement applied on top; widget size 250–800 px. Exposed that the editor's rotation had the opposite sign from TinyPedal's `rotate_coordinate` — the editor now uses the widget's convention and `version < 3` files are migrated by negating the angle (Imola ‑96° → +96°, same picture). Export is `version: 3` |
| `04-ship-placements` | ✅ `f653a8c` | The four driver placements (Imola ‑89°, Paul Ricard ELMS 0°, Silverstone National 35°, Monza Curva Grande 0°) are **packaged into TinyPedal** by the export script as `label_offset_m` + `display_orientation` (schema 2), and the widget draws them: `plan_turn_labels` places offset labels first (falling back to the rule only if one would overlap or leave the widget) and `map_orientation()` adopts the packaged rotation unless the user sets one (`use_track_orientation` to opt out; negative angles no longer clamped to 0). New sibling test `test_shipped_placements.py` (46 assertions) + wrapper here |
| `05-pr-400px-placement` | ✅ `d1a9d3a` | Paul Ricard ELMS re-tuned at the 400 px preview and re-shipped (16/16 labels, 0 dropped, 0 overlaps at 400 and 600 px; placement stretch median 1.00). Fixed why the 400 px check misled: the preview measured with the page font, while the widget uses Consolas Bold + 0.085 em stroke — the preview now mirrors that. The widget now **stretches a colliding placement** along its own direction before falling back to its rule, and the render harness passes `units_per_metre` like the real widget |
