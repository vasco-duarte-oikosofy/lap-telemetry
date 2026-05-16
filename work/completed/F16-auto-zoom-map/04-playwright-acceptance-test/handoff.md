# Slice 04 — Handoff

## What's on disk

### New files
- `dev/scripts/test_f16_auto_zoom_acceptance.js` — Playwright acceptance test (21 assertions, 7 scenarios)
- `var/test-output/f16-auto-zoom-acceptance-report/` — Test report + screenshots

### Modified files
- `product/web/js/main.js` — Added debug hooks: `__setZoomRange`, `__clearZoomRange`, `__getZoomRange`, `__computeSegmentBounds`
- `product/web/js/debugHooks.js` — Added `mapAutoZoom` to `__setFeatureFlag` re-render list
- `product/web/dist/compare.html` — Rebuilt bundle (includes new debug hooks)
- `package.json` — Registered `test_f16_auto_zoom_acceptance.js` in test chain

### Debug hooks added (product code)

| Hook | Purpose |
|------|---------|
| `window.__setZoomRange(start, end)` | Set `currentZoomRange` and re-render map |
| `window.__clearZoomRange()` | Reset to full-track and re-render map |
| `window.__getZoomRange()` | Read current `currentZoomRange` |
| `window.__computeSegmentBounds(lapA, range)` | Wrap `computeSegmentBounds` for test access |

## Test scenarios

| # | Scenario | Assertions | Status |
|---|----------|-----------|--------|
| SC1 | Default state — full track, no auto-zoom | 3 | PASS |
| SC2 | Auto-zoom activates on zoom range | 4 | PASS |
| SC3 | Auto-zoom resets on clear | 2 | PASS |
| SC4 | Toggle mapAutoZoom with no zoom range — no movement | 1 | PASS |
| SC5 | computeSegmentBounds deterministic | 2+1 | PASS |
| SC6 | mapAutoZoom + mapZoomPan coexist | 5 | PASS |
| SC7 | Screenshot artifacts exist | 4 | PASS |

## Feature flags live

- `mapAutoZoom` (default: false) — toggles auto-zoom feature
- `mapLinkedHighlight` (default: false) — prerequisite for auto-zoom effect

## Known issues (validating Bugs 5–9)

- **Bug 7** (`computeSegmentBounds` uses X as distance): The test validates determinism only, not correctness. When Bug 7 is fixed, `computeSegmentBounds` will return geographically correct bounds and auto-zoom will show a larger portion of track. The pixel-matching assertions may need adjustment at that point.
- **Bug 5** (double-click reset broken with mapAutoZoom): SC6 tests that double-click returns scale to 1 and that the zoom range persists. It does NOT test that double-click returns to full-track view (because Bug 5 is open).
- **Bug 6** (map moves when enabling mapAutoZoom with no selection): SC4 validates this is NOT happening — all pixels match.

## Deferred

- Visual regression with pixel diff — not in scope per prompt non-goals
- SC2 pixel change is only 2/25 due to Bug 7; will improve when bug is fixed