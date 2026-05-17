# Slice 01: U3c — TC active panel shows both laps in session/ref colours

## Problem

The TC active panel (`id: 'tc'`) currently renders a **single green trace** using `color: 'var(--throttle)'` with only `trace: 'session'`. In comparison mode the user expects to see both laps — session (solid, blue) and reference (dashed, orange) — so they can compare TC activation zones between laps. Currently the ref lap is **missing entirely**.

## Current code

`product/web/js/panelConfig.js`, TC panel definition (around line 28):

```js
{ id: 'tc', label: 'TC active', height: 50,
  channels: [
    { col: 'tc_active', trace: 'session', color: 'var(--throttle)', dash: false, step: true },
  ],
  yFixed: [0, 1], yStep: 1, midline: 0.5, zeroline: false },
```

## Target code

Replace the single channel with two channels — session and ref — using lap-identity colours:

```js
{ id: 'tc', label: 'TC active', height: 50,
  channels: [
    { col: 'tc_active', trace: 'session', color: 'var(--session)', dash: false, step: true },
    { col: 'tc_active', trace: 'ref', color: 'var(--ref)', dash: true, step: true },
  ],
  yFixed: [0, 1], yStep: 1, midline: 0.5, zeroline: false },
```

Key changes:
- **Session trace**: `color: 'var(--throttle)'` → `color: 'var(--session)'`
- **Added ref trace**: `{ col: 'tc_active', trace: 'ref', color: 'var(--ref)', dash: true, step: true }`
- Both traces keep `step: true` since TC is a binary on/off signal

## Acceptance criteria

1. TC active panel shows **two traces** in comparison mode: session (solid blue) and ref (dashed orange)
2. In single-lap mode, only the session trace renders (existing behaviour preserved)
3. All existing tests pass: `bash scripts/test-summary.sh` exits 0
4. `npm run build` succeeds and `dist/compare.html` is current

## Scope

- `product/web/js/panelConfig.js` — change TC panel channel definitions
- No schema, recorder, or HTML changes required