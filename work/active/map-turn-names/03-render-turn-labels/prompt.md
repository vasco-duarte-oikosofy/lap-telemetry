# Slice 03 — Render turn labels on the circuit map

Draw the baked `turns` labels in the compare app (spec:
`docs/specs/MAP_TURN_NAMES.md`).

1. `product/web/js/turnLabels.js` — pure planner: alternating sides, text tiers,
   two nudge caps, no-overlap candidate search. Text metrics injected.
2. `product/web/js/turnLabelsRender.js` — canvas painter + canvas text metrics.
3. Wire into `renderWalkingSkeleton()` (the map is canvas-rendered; the SVG twin
   is hidden), gated by `features.mapTurnLabels`, **ON by default**.
4. Tests first: `test_turn_labels.js` (pure planner) and
   `test_turn_labels_ui.js` (Playwright: real session, 8 Silverstone labels, no
   overlaps, inside the map, adjacency, painted pixels, flag off, no-turns track).
5. A committed 2-lap Silverstone fixture, because the old dev fixtures store a
   constant position and collapse the map transform.
