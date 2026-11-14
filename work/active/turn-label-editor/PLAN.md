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
