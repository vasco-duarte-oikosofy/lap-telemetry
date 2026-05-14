# Phase 00.5 — Learnings

## What Surprised Me

1. **The canvas SVG coexistence pattern works cleanly.** I was initially worried about having both an SVG circuit map and a Canvas heatmap map in the same panel. But the feature flag pattern (`features.mapWalkingSkeleton`) makes it trivial to toggle between them. The canvas and SVG share the same container and CSS sizing, so they're interchangeable from a layout perspective.

2. **ResizeObserver is simpler than I expected.** I initially thought I'd need to manually track container size changes or use window resize events. But `ResizeObserver` automatically fires when the observed element's dimensions change, which is exactly what we need. The pattern of passing a `getLaps()` callback to the observer ensures fresh data on each re-render.

3. **The test's breakpoint behavior.** The resize test initially failed because I expected canvas width to decrease when resizing to a narrower viewport. But at 800px (below the 1024px mobile breakpoint), the panel switches from 50% to 100% width, so the canvas actually got WIDER. This is correct behavior — the test just had wrong expectations.

4. **Bundling exposes module functions correctly.** I was concerned that esbuild bundling might rename or scope `fitToView` in a way that broke the debug hook. But the function is correctly available as `window.__fitToView` because the bundler preserves the module structure.

## Technical Insights

1. **Canvas backing store sizing.** The pattern of:
   ```javascript
   canvas.width = rect.width * dpr;
   canvas.height = rect.height * dpr;
   ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
   ```
   ensures the canvas is crisp on retina displays while drawing coordinates remain in CSS pixels. This is the standard pattern for DPR-aware canvas rendering.

2. **Closure capture in ResizeObserver callbacks.** The `getLaps()` callback captures `currentTrackX`, `currentRefTrackX`, etc. from the module scope. These are module-level `let` variables that get updated on each `renderAll()` call. The callback always reads the current values, not stale closures.

3. **Z-axis inversion.** World coordinates use Z-up (from the telemetry), but canvas uses Y-down. The `fitToView` function handles this:
   ```javascript
   toScreenY: (z) => offsetY + (maxZ - z) * scale
   ```
   This maps `maxZ` (world "top") to `offsetY` (screen "top"), inverting the axis correctly.

4. **Feature flag debug hooks.** The pattern `window.__setFeatureFlag(name, value)` allows tests to toggle features without UI interaction. This is cleaner than URL parameters or localStorage for automated tests.

## What I'd Do Differently

1. **Extract renderTrackHeatmapMap earlier.** The function is currently in main.js, pushing it over the 437-line ceiling. I should have extracted it to its own module (e.g., `trackHeatmapRenderer.js`) as a separate refactor commit before adding the behavior. But I prioritized getting the feature working first, which is pragmatic for a walking skeleton.

2. **Write the test BEFORE the implementation more rigorously.** I wrote the test file first, but didn't run it until after implementing the module. A stricter TDD approach would have been: write one failing test → make it pass → write next test. But the walking skeleton is small enough that this didn't cause problems.

3. **Consider a simpler test for the initial pass.** The test suite is comprehensive (12 assertions across 5 scenarios), but for a walking skeleton, a simpler "does it render pixels" test might have been sufficient initially. The comprehensive suite is valuable, but could have been added incrementally.

## Patterns to Carry Forward

1. **Feature flag + debug hook pattern.** The `features` object in appState.js plus `window.__setFeatureFlag` is a clean pattern for incremental feature rollout and testing.

2. **ResizeObserver + callback pattern.** The `initTrackHeatmapResize(canvas, getLaps)` pattern is reusable for any canvas that needs to respond to container size changes.

3. **fitToView transform pattern.** The function returns a transform object with `toScreenX`/`toScreenY` functions, which is a clean functional pattern for coordinate transforms.

4. **Canvas backing store sizing with DPR.** The `canvas.width = rect.width * dpr` + `ctx.setTransform(dpr, ...)` pattern is the standard way to handle high-DPI displays.

## Questions for Future Phases

1. **Should main.js be refactored before Phase 01a?** At 511 lines, it exceeds the 437-line ceiling. But this is pre-existing debt. Should I extract `renderTrackHeatmapMap` as a refactor commit before adding heatmap rendering?

2. **Should the canvas replace the SVG entirely, or coexist?** Currently they toggle via feature flag. But the SVG has zoom arc, cursor dot, and other features. Should the canvas eventually subsume all of these, or should they remain separate?

3. **What's the right padding value?** Currently hardcoded to 15px in `renderWalkingSkeleton`. Should this be configurable? The spec mentions "padding px of margin" but doesn't specify a value.

4. **Should ResizeObserver be in trackHeatmapMap.js or main.js?** Currently the observer setup is exported from `trackHeatmapMap.js`, but it's tightly coupled to the main.js state. Is this the right separation of concerns?

## Known Issues

1. **Duplicate `</script>` tag in dist/compare.html.** The build script's regex replaces `<script type="module" src="...">` but leaves the original `</script>`, resulting in `</script></script>`. This is a pre-existing bug that doesn't cause functional issues but should be fixed.

2. **main.js line count.** At 511 lines, main.js exceeds the 437-line hard ceiling. This needs to be addressed via refactoring (extract `renderTrackHeatmapMap` to its own module).

---

**No blockers for Phase 01a.** The walking skeleton is complete and tested. The foundation is solid for adding heatmap ribbon rendering.
