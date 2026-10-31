# Handoff — Slice 03 (labels rendered in the product)

## What is on disk

| Path | What it is |
|---|---|
| `product/web/js/turnLabels.js` | **new** — pure planner (`planTurnLabels`), text tiers, alternating sides, nudge caps, no-overlap search. ~170 lines, no DOM. |
| `product/web/js/turnLabelsRender.js` | **new** — canvas painter (`drawTurnLabels`), canvas text metrics (`canvasMeasure`), last-drawn accessors for tests. |
| `product/web/js/trackHeatmapMap.js` | draws the labels after the polylines + start/finish tick; theme colours for text and halo. |
| `product/web/js/trackHeatmapController.js` | `buildOpts()` passes `showTurnLabels: !!features.mapTurnLabels`. |
| `product/web/js/appState.js` | `mapTurnLabels: true` (**ON by default**; it also appears in the feature-flag menu automatically). |
| `product/web/js/debugHooks.js` | `window.__turnLabels()` → `{ labels, dropped }` of the last frame. |
| `dev/scripts/test_turn_labels.js` | **new** — 12 planner assertions (sides, caps, tiers, overlap, bounds, determinism). |
| `dev/scripts/test_turn_labels_ui.js` | **new** — 11 Playwright assertions on a real render. |
| `dev/sessions/session_20261031T051245Z_silverstone-international-circuit_lmu_quali_2laps.parquet` | **new fixture** (463 KB, 2 laps) sliced from a real session: the old dev fixtures store a constant `pos_x_m/pos_z_m`. |
| `package.json` | both tests in `npm test` + `testFeatures["map-turn-names"]` (7 scripts). |

## Verified

- `--feature map-turn-names`: **259 assertions, ALL PASS**.
- Full suite `--pw`: 1313 passed, 6 failed — the same pre-existing Windows
  `ERR_UNSUPPORTED_ESM_URL_SCHEME` harness failures.
- Live behaviour (Silverstone International, 8 turns): 8 labels `T1 Abbey` …
  `T8 Club`, zero overlaps, all inside the map, worst apex→box 6 px against a
  16 px budget, and bright pixels confirmed inside each label rect.

## Gotchas for the next agent

- The map is **canvas**, not SVG. Label drawing belongs in
  `renderWalkingSkeleton()`; anything added to `#circuit-map-svg` is invisible.
- `getBBox()` is useless here (SVG is `display:none`) — measure with canvas.
- The canvas viewport is rectangular (650×514 in the test); bounds checks need
  `mapWidth`/`mapHeight`, not `mapSize`.
- `trackName` is `null` on the cursor-driven re-render path — a null name must
  skip, not clear.
- `__setFeatureFlag()` only flips state; tests must force a re-render (resize).

## Deferred

- Label interaction (click-to-zoom, cursor linking) — separate mission.
- TinyPedal port (`../tinypedal`, Qt/QPainter) — the planner is pure and every
  constant is documented for it.
- Tracks whose coaching models are still uncurated have no labels (8 outlines).
