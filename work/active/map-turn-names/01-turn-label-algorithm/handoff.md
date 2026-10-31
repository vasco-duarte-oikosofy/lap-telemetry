# Handoff — Slice 01 (turn label placement spike)

**Status: awaiting user review of the images.** No product code was touched;
`product/` is byte-identical to the previous commit.

## What is on disk (all under `artifacts/`)

| File | What it is |
|---|---|
| `bake_anchors.py` | Bakes `apex_s_m` → world `x,y` + outward normal + label anchor. Unwrap-aware (see learnings). Prototype of slice 02's bake step. |
| `render_labels.mjs` | Playwright renderer + measurement (`overlaps / clipped / clearance / dropped`), writes PNGs and `overlap-report.json`. Prototype of slice 03's layout math. |
| `anchors-<slug>.json` | Baked anchors for `silverstone-international-circuit` (8 turns) and `monza-curva-grande-circuit` (10 turns) — the proposed `turns` block shape. |
| `labels-<slug>-<tag>.png` | 7 configs × 2 tracks at `deviceScaleFactor 3`. The review set. |
| `ALGORITHM.md` | The algorithm, every constant, the measurement tables and the slice 02/03 recommendation. |
| `overlap-report.json` | Machine-readable version of the tables (per-label widths and clearances). |

## Review order (suggested)

1. `labels-silverstone-international-circuit-00-250-raw-official.png` — the raw
   placement: 1 overlap and 2 clipped labels.
2. `...-08-250-push-short.png` — after push/clamp/drop with short names: 7 of 8
   shown, nothing clipped, nothing overlapping.
3. `...-10-250-numbers.png` — numbers-only at the same size: all 8 shown.
4. `labels-monza-curva-grande-circuit-00-250-raw-official.png` vs
   `...-00b-250-raw-short.png` — the long-name problem (113 px → 60 px widest).
5. `...-11-120-numbers.png` vs `...-09-120-push-short.png` — the TinyPedal-sized
   map: names collapse (5 of 10), numbers hold (7 of 10).

## Decisions the review needs to settle

1. **Chained sub-turns**: accept dropping 1–2 labels per chicane complex, or add
   a bake-time `chain_id` and render one label per chain (`Roggia`, `Ascari`)?
   Recommendation: `chain_id`.
2. **`short_name`**: add the curated field to the `turns` schema (recommended),
   or render official names and accept 113 px labels?
3. **Degradation thresholds**: `≥200 px` names, `150–200 px` short names at
   `fontRatio 0.026`, `<150 px` numbers only — confirm.

## Still open (not started)

- Slices 02–05 in `PLAN.md` (schema + preservation guard, renderer + flag,
  backfill, declutter).
- The spike does not cover: label rotation, per-lap label positions (anchors are
  static), heatmap-mode legibility, or the National/GP Silverstone outlines (no
  outline yet for those).
