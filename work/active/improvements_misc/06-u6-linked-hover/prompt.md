# Slice 06: U6 — Linked hover: chart cursor drives the existing map hover UI

## Problem

When hovering over the chart panels, the canvas circuit map should show the same
position feedback that direct map hover shows: the perpendicular track tick **and**
the floating throttle/brake readout. The first implementation only drew a linked
tick by adding a second hover rendering path, so it bypassed `mapHover.js` and did
not show the readout.

## Current behaviour

- `mapHover` (feature flag, default off): pointer hover on the map canvas shows a
  perpendicular tick across the track ribbons and a floating readout. This works
  through `mapHover.js`, which owns hover state, `sLookup()`, readout DOM, readout
  positioning, and renderer invalidation.
- `cursor.js` chart hover computes `binIdx` (track distance in metres), positions
  the SVG `cursor-dot` circle on the legacy SVG map, and shows the tooltip over the
  charts.
- Commit `0c09bf0` added `linkedHoverState` / `showLinkedHover` as a parallel map
  hover path. That violates DRY and produces incomplete behaviour: tick without the
  `mapHover` throttle/brake readout.

## Target behaviour

When **both** `mapHover` and `mapLinkedHover` feature flags are enabled:
- Moving the mouse over the chart panels drives the existing map-hover UI at the
  same track distance (`s = binIdx`).
- The canvas map shows the same hover tick and floating readout used by direct map
  hover, including throttle/brake information.
- Leaving the chart area clears the linked hover UI.
- Starting a chart drag selection clears the linked hover UI.
- Direct pointer hover on the map takes priority over linked chart hover.
- With either flag off, linked chart hover is inactive and existing behaviour is
  unchanged.

## Implementation choices

### Design rule

`mapHover.js` is the single owner of map hover behaviour. Chart hover is only a
second input source that supplies a distance. Do **not** add another renderer branch
or another hover-state option for linked hover.

The renderer should continue to know only this:

```js
if (options.showHover && options.hoverState) {
  drawHoverTick(ctx, options.hoverState, transform, ribbonWidthPx, ribbonGapPx);
}
```

### 1. `appState.js` — feature flag only

Add to `features`:

```js
mapLinkedHover: false,  // Drive mapHover UI from chart cursor distance
```

Do **not** add `state.linkedHoverDist`. Linked hover is transient interaction state
owned by `mapHover.js`, not application state.

Add `mapLinkedHover` to the map-rendering feature flag allowlist in `debugHooks.js`.

### 2. `mapHover.js` — expose linked-distance input, reuse same hover pipeline

Add a small public API to the object returned by `createMapHover()`:

```js
setLinkedDistance(s)
clearLinkedDistance()
```

Internally, avoid duplicate UI code by extracting helpers that both direct pointer
hover and linked chart hover use:

- Build a hover state from a track distance:
  - call `sLookup(lapA.raw, s)` to get the nearest/interpolated point
  - use the current map transform to compute `screenX` / `screenY`
  - populate the same hover-state shape used by pointer hover:
    `{ s, screenX, screenY, lapASample, lapBSample, nearest }`
- Apply a hover state:
  - set `hoverState`
  - update or hide the readout DOM
  - position the readout
  - call `onUpdate?.(hoverState)` so the controller re-renders the map tick

Priority rule:
- Direct pointer hover wins while the pointer is active over the map.
- Linked distance is allowed to update stored linked state, but it must not replace
  an active direct pointer hover.
- When direct pointer hover leaves, re-apply any current linked distance if present;
  otherwise clear hover state.

### 3. `trackHeatmapController.js` — bridge chart distance to `mapHover`

Keep controller rendering simple:

```js
showHover: !!features.mapHover,
hoverState: mapHover ? mapHover.getState() : null,
```

Do **not** import `sLookup` or compute `linkedHoverState` in the controller.

Expose a controller method/callback, for example:

```js
function setChartHoverDistance(s) {
  if (!features.mapHover || !features.mapLinkedHover || !mapHover) return;

  if (s == null) mapHover.clearLinkedDistance();
  else mapHover.setLinkedDistance(s);
}
```

Ensure it triggers the normal map-hover invalidation path through `mapHover`'s
`onUpdate` callback. If `mapHover` has not been created yet and both flags are on,
create it before applying the linked distance.

### 4. `cursor.js` — report distance only

`cursor.js` should not import `features`, should not mutate app state, and should
not know how map hover is rendered.

Accept a callback from `main.js`, for example:

```js
initCursorAndZoom(renderAll, getRenderState, onChartHoverDistance);
```

On chart cursor move inside the plot:

```js
onChartHoverDistance?.(binIdx);
```

On chart leave, outside plot, or drag start:

```js
onChartHoverDistance?.(null);
```

This keeps chart cursor code responsible only for reporting the chart cursor
position.

### 5. `trackHeatmapMap.js` — no linked-hover-specific code

Do not add `showLinkedHover`, `linkedHoverState`, or a second `drawHoverTick()` call.
The existing `hoverState` path should draw both direct map hover and chart-linked
hover.

### 6. `main.js` — wire chart cursor to controller

Pass the controller's chart-hover-distance callback into `initCursorAndZoom()`.
The callback name can vary, but the dependency direction should stay:

```text
cursor.js reports distance → controller delegates to mapHover.js → renderer draws existing hoverState
```

## Files changed

| File | Change |
|------|--------|
| `product/web/js/appState.js` | Add `mapLinkedHover` flag only; no linked hover app state |
| `product/web/js/mapHover.js` | Add linked-distance public API and reuse existing hover-state/readout pipeline |
| `product/web/js/cursor.js` | Report chart hover distance/clear events via callback only |
| `product/web/js/trackHeatmapController.js` | Delegate chart hover distance to `mapHover`; keep one `hoverState` option |
| `product/web/js/trackHeatmapMap.js` | Keep existing single `drawHoverTick()` path; remove linked-specific rendering |
| `product/web/js/main.js` | Wire cursor distance callback to the track heatmap controller |
| `product/web/js/debugHooks.js` | Add `mapLinkedHover` to feature flag allowlist |

## Acceptance criteria

1. With `mapHover` + `mapLinkedHover` both ON: moving the mouse over the chart panels
   shows the same map hover tick and throttle/brake readout as direct map hover,
   positioned at the chart cursor distance.
2. Leaving the chart area clears the linked hover UI.
3. Starting a chart drag selection clears the linked hover UI.
4. Direct map hover takes priority over linked chart hover.
5. With either flag OFF: no linked chart hover UI appears and existing behaviour is
   unchanged.
6. The renderer has only one hover tick path: `options.hoverState` + `drawHoverTick()`.
7. All existing tests pass (`bash scripts/test-summary.sh` exits 0).
8. `npm run build` succeeds.
