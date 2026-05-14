# Phase 04 — Learnings

## What surprised me

1. **Playwright `page.evaluate()` only accepts a single argument.** I tried passing `(x, y)` as two arguments to `page.evaluate()` and hit `Error: Too many arguments`. Wrapping them in an object `{ x, y }` fixed it. This is a sharp edge when porting tests from other environments.

2. **`getBoundingClientRect` shimming breaks pointer-event coordinate math.** Previous synthetic tests shimmed `canvas.getBoundingClientRect` to return fixed dimensions for deterministic rendering. That works fine when tests only assert rendered pixels, but hover hit-testing needs real `left/top` values to convert `clientX/clientY` into canvas-local coordinates. The cleanest fix was to create a dedicated synthetic canvas positioned at `left:0;top:0` with `position:absolute` so its real bounding box is already deterministic — no shim needed.

3. **`currentLapBRaw` did not include `throttle` or `brake`.** The Phase 01b implementation only stashed `s`, `x`, `z` for the reference lap. Phase 4's readout needs Lap B throttle/brake values, so I had to extend `currentLapBRaw` in `main.js`. This is a good reminder that "raw" data structures accumulate fields as downstream phases need them.

4. **`offsetX/Y` on synthetic PointerEvents isn't enough.** I initially hoped `e.offsetX` would bypass the bounding-box problem, but browsers compute `offsetX` from the element's bounding client rect, so the same shim that breaks `getBoundingClientRect` also breaks `offsetX`. Dispatching events with explicit `clientX`/`clientY` on a canvas at a known viewport position is the reliable path.

## Anything the next agent needs to know

- The hover spatial index is a **uniform grid** (20m cells, 3×3 neighbor search). It is rebuilt on every render via `mapHover.rebuild()`. For a ~5 km lap this is trivial (< 1 ms). If later phases need to optimize for very long tracks or many laps, the grid could be upgraded, but it's not a bottleneck now.
- The readout DOM is created lazily by `ensureReadout(panel)` inside `mapHover.js`. It is appended to `canvas.parentElement` (the `#circuit-map-panel`). If the panel structure ever changes, that selector needs to change too.
- The white tick drawing uses a **screen-space tangent approximation** (`toScreenX(x+0.5) - toScreenX(x)`) rather than world-space tangent. This is correct because the tick must be perpendicular to the *screen projection* of the racing line, not the world-space line. At extreme zooms or near poles this could theoretically distort, but for a top-down track map it is exact enough.
- `mapHover` is **self-contained** — it attaches its own pointer listeners and tracks `isDragging` independently of `mapInteraction.js`. This keeps the modules decoupled but means both modules listen to `pointerdown`/`pointerup` on the same canvas. In practice this works because Pointer Events support multiple independent listeners.
