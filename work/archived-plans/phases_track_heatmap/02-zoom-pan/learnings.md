# Phase 02 — Learnings

## What surprised me

1. **Wheel-event zoom centering requires base-transform awareness.** The naive `pan += mx * (1 - zoomRatio)` only works when the origin is (0,0). Because our fit-to-view includes a base offset that centers the track, the correct formula is `newPan = oldPan * zoomRatio + (cursorScreen - baseOffset) * (1 - zoomRatio)`. Keeping a `baseTransformRef` in the interaction module and updating it on every render was the cleanest fix.

2. **Pointer Events vs. Mouse Events — `setPointerCapture` is non-optional.** Without capturing the pointer on `pointerdown`, dragging outside the canvas (common when panning) loses the gesture. Calling `canvas.setPointerCapture(e.pointerId)` in the down handler and releasing on up/cancel solved this.

3. **Ribbon screen-pixel constancy is already satisfied by screen-space extrusion.** The existing `drawRibbon`/`drawDualRibbons` compute normals from screen-space points and offset by a constant pixel distance. No code changes were needed for Phase 2 — the composed transform simply makes the centerline points spread apart, and the ribbon thickness stays constant.

4. **Eager interaction init is required for tests without data.** We initially initialized `createMapInteraction` only when both laps' track data was present. The Playwright test enables the feature flag but doesn't load a session, so the canvas is visible but there is no data. Moving the interaction initialization before the early-return data check fixed the test and matches real-world behavior (users may enable the flag before loading laps).

## Deferred TODOs

- The zoom indicator is a plain text span. In Phase 6.5 we may want to add +/- buttons around it.
- `drawTrackOutline` still uses debug magenta/cyan instead of the spec's `rgba(120,120,120,0.4)`.
- No keyboard shortcuts yet (Phase 6.4).
- No minimap (Phase 6.6).
