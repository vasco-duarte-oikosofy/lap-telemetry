# Handoff — Slice 05 (type size in the compare app)

## What changed

| File | Change |
|---|---|
| `product/web/js/turnLabels.js` | `TURN_LABEL_CONFIG.fontMax` 8 → **18** (ceiling now binds above ~783 px `mapSize`, so the compare app scales freely). |
| `product/web/js/turnLabelsRender.js` | halo width is `max(1.4, fontSize * 0.16)` px instead of a fixed 1.6 px. |
| `dev/scripts/test_turn_labels.js` | size assertions now pin 574 px → 13.2 px, 622 px → 14.31 px, ratio applied, ceiling at 1500 px, and 250/120 px unchanged. |
| `dev/scripts/test_turn_labels_scale.js` | **new** Playwright test: all 14 packaged outlines × 3 real viewports (500×454, 650×574, 910×622) → 173/173 labelled, 0 overlaps, 0 off-map, every named turn keeps its name, 250 px still 5.75 px. |
| `docs/specs/MAP_TURN_NAMES.md` | type-size section with the measurement and the new constants. |

## Numbers

| viewport (map canvas) | fontSize | labels | names | overlaps |
|---|---|---|---|---|
| 500×454 (narrow window) | 10.44 px | 173/173 | 136/136 named | 0 |
| 650×574 (1400×1000 window) | 13.2 px | 173/173 | 136/136 named | 0 |
| 910×622 (1920×1080 window) | 14.31 px | 173/173 | 136/136 named | 0 |

250 px map → 5.75 px, unchanged (the TinyPedal range is untouched).

## Notes for the next agent

- If a user reports "too small" again, measure `window.__turnLabels()[0].h` and
  the canvas CSS size before touching constants; the ratio is `0.023`.
- The 37 unnamed turns (`T5` with no name) are missing data in their coaching
  models, not a placement failure.
