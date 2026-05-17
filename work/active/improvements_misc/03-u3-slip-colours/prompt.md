# Slice 03: U3 — Fix Slip angle panel trace colours to use session/ref identity

## Problem

The Slip angle panel (`id: 'slip'`) currently colours traces by **wheel identity** — FL traces use `var(--slip-fl)` (purple) and FR traces use `var(--slip-fr)` (teal). This breaks the app-wide convention that session traces are `var(--session)` (blue, solid) and ref traces are `var(--ref)` (orange, dashed). The result: in the slip panel, the user cannot tell at a glance which traces belong to which lap (session vs ref), because both session and ref traces for the same wheel share the same colour and differ only by dash pattern.

Every other comparison panel (speed, throttle, brake, RPM, gear, steering) already uses lap-identity colours. The slip panel should follow the same convention.

## Current code

`product/web/js/panelConfig.js`, slip panel definition (around line 53):

```js
{ id: 'slip', label: 'Slip angle FL / FR (deg)', height: 80,
  channels: [
    { col: 'slip_angle_fl_deg', trace: 'session', color: 'var(--slip-fl)', dash: false },
    { col: 'slip_angle_fl_deg', trace: 'ref',     color: 'var(--slip-fl)', dash: true },
    { col: 'slip_angle_fr_deg', trace: 'session', color: 'var(--slip-fr)', dash: false },
    { col: 'slip_angle_fr_deg', trace: 'ref',     color: 'var(--slip-fr)', dash: true },
  ],
  yFixed: null, yStep: 2, zeroline: false, niceSteps: [0.5, 1, 2, 5] },
```

## Target code

Replace all four channel colours with lap-identity colours — `var(--session)` for session traces, `var(--ref)` for ref traces:

```js
{ id: 'slip', label: 'Slip angle FL / FR (deg)', height: 80,
  channels: [
    { col: 'slip_angle_fl_deg', trace: 'session', color: 'var(--session)', dash: false },
    { col: 'slip_angle_fl_deg', trace: 'ref',     color: 'var(--ref)',    dash: true },
    { col: 'slip_angle_fr_deg', trace: 'session', color: 'var(--session)', dash: false },
    { col: 'slip_angle_fr_deg', trace: 'ref',     color: 'var(--ref)',    dash: true },
  ],
  yFixed: null, yStep: 2, zeroline: false, niceSteps: [0.5, 1, 2, 5] },
```

**Design note:** FL and FR traces of the same lap now share the same colour (blue for session, orange for ref). This is intentional and matches every other panel. FL vs FR cannot be distinguished by colour alone, but:
- They differ in shape (FL and FR slip angles are rarely identical).
- The cursor tooltip identifies which channel each value belongs to.
- The primary visual task — comparing session vs ref — is now consistent with all other panels.

## Acceptance criteria

1. Slip angle panel shows **four traces** with lap-identity colours: session FL (solid blue), session FR (solid blue), ref FL (dashed orange), ref FR (dashed orange)
2. `var(--slip-fl)` and `var(--slip-fr)` are **no longer referenced** in the slip panel definition
3. All existing tests pass: `bash scripts/test-summary.sh` exits 0
4. `npm run build` succeeds and `dist/compare.html` is current

## Scope

- `product/web/js/panelConfig.js` — change slip panel channel colours only
- No schema, recorder, CSS, or HTML changes required
- `var(--slip-fl)` and `var(--slip-fr)` CSS variables may remain defined in `styles.css` for potential future use; do **not** remove them