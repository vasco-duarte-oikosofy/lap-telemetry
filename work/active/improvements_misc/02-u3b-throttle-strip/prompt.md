# Slice 02: U3b — Remove TC activity strip from Throttle panel

## Problem

The Throttle panel renders a TC activity strip (`tc_active`) alongside the throttle trace. TC is its own dedicated panel (`id: 'tc'`) — showing it again inside Throttle is redundant and makes the throttle trace harder to read.

## Current code

`product/web/js/panelConfig.js`, Throttle panel definition:

```js
{ id: 'throttle', label: 'Throttle', height: 60,
  channels: [
    { col: 'throttle_norm', trace: 'session', color: 'var(--session)', dash: false },
    { col: 'throttle_norm', trace: 'ref', color: 'var(--ref)', dash: true },
  ],
  yFixed: [0, 1], yStep: 0.5, zeroline: false,
  activityStrip: { col: 'tc_active', color: 'var(--throttle)' } },
```

## Target code

Remove the `activityStrip` entry:

```js
{ id: 'throttle', label: 'Throttle', height: 60,
  channels: [
    { col: 'throttle_norm', trace: 'session', color: 'var(--session)', dash: false },
    { col: 'throttle_norm', trace: 'ref', color: 'var(--ref)', dash: true },
  ],
  yFixed: [0, 1], yStep: 0.5, zeroline: false },
```

The Brake panel keeps its `activityStrip` for ABS since there is no dedicated ABS panel.

## Acceptance criteria

1. Throttle panel no longer shows the TC activity strip below the throttle traces.
2. Brake panel continues to show the ABS activity strip (unchanged).
3. TC panel continues to show both session and ref traces (unchanged).
4. All existing tests pass (`bash scripts/test-summary.sh` exits 0).
5. `npm run build` succeeds and `dist/compare.html` is current.

## Files changed

| File | Change |
|------|--------|
| `product/web/js/panelConfig.js` | Remove `activityStrip` from Throttle panel definition |

## Non-goals

- Do not modify the Brake panel's ABS activity strip.
- Do not modify the TC panel.
- Do not add new tests for this visual change unless existing tests fail.
