# Handoff — U3c TC panel

## State on disk

- `product/web/js/panelConfig.js` — TC panel now has two channels (session + ref) using `var(--session)` and `var(--ref)` colours.
- Committed on `main` as `1c20173`.

## What changed

- TC panel `color: 'var(--throttle)'` → `color: 'var(--session)'` for the session trace.
- Added ref trace: `{ col: 'tc_active', trace: 'ref', color: 'var(--ref)', dash: true, step: true }`.

## Verification

- `bash scripts/test-summary.sh` — 1074 assertions, all pass.
- `npm run build` — succeeds, `product/dist/compare.html` is current.

## Deferred

- ABS panel (`id: 'abs'`) has the same single-trace issue (uses `var(--brake)` instead of `var(--session)`/`var(--ref)`). Separate slice needed.