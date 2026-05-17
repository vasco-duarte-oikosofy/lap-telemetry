# Handoff — U3b Throttle TC strip removal

## State on disk

- `product/web/js/panelConfig.js` — Throttle panel `activityStrip` removed.
- `dev/scripts/test_m6.js` — updated to reflect that throttle panel no longer has TC strips.
- Committed on `main`.

## What changed

- Removed `activityStrip: { col: 'tc_active', color: 'var(--throttle)' }` from the Throttle panel definition.
- Brake panel's ABS activity strip remains unchanged.
- Test `test_m6.js` assertion updated: throttle panel should now have 0 TC strip rects (was previously asserting > 0).

## Verification

- `bash scripts/test-summary.sh dev/scripts/test_m6.js` — 26 assertions pass.
- `bash scripts/test-summary.sh` — 1081 assertions across 45 scripts pass.
- `npm run build` — succeeds, `product/dist/compare.html` is current.

## Deferred

None for this slice.
