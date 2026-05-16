# Phase 0.1 — Learnings

## What Surprised Me

1. **The edit tool's exact matching is both a blessing and a curse.** I initially tried to make multiple small edits to `panels.js`, but the tool requires exact text matches including whitespace. After several failed attempts, I realized it's faster to rewrite the entire file when making pervasive changes (every coordinate calculation needed updating). The backup/restore pattern helped verify changes incrementally.

2. **SVG `preserveAspectRatio` behavior.** I initially thought the panels needed complex viewBox calculations. The insight: set `viewBox="0 0 ${containerWidth} ${height}"` dynamically and use `preserveAspectRatio="none"` to let the browser handle the stretching. This is simpler than manual coordinate transforms.

3. **The existing codebase was already well-structured.** The separation between `panels.js` (rendering logic) and `main.js` (application state + orchestration) made it trivial to add the `containerWidth` parameter. No refactoring was needed before implementing the feature — the architecture supported it out of the box.

## Technical Insights

1. **Scale factor pattern works well:** Computing `scaleX = containerWidth / SVG_W` once and deriving all scaled values from it keeps the math consistent and avoids accumulation of rounding errors.

2. **Client width measurement timing:** Measuring `panelsDiv.clientWidth` inside the render loop works because the DOM has already been updated by Phase 0's CSS. The container width is stable by the time `renderAll()` runs.

3. **Backward compatibility:** The default parameter `containerWidth = SVG_W` means any external callers (e.g., tests, debug hooks) that don't pass the new parameter still work correctly. This is important for not breaking existing code.

## What I'd Do Differently

1. **Write the test first, more rigorously.** I created a test file but didn't run it before implementing. The existing test suite passing was sufficient validation, but a dedicated responsive test would catch edge cases earlier.

2. **Consider a ResizeObserver for dynamic updates.** Currently, panels render at the container width at render time. If the user resizes the window after rendering, the panels don't re-render at the new width. A ResizeObserver could trigger re-renders on resize, but this is out of scope for Phase 0.1 (it would be a Phase 2 enhancement alongside zoom/pan).

## Patterns to Carry Forward

1. **Optional parameters with defaults** for backward compatibility when adding new configuration to rendering functions.

2. **Scale factor computation** as a reusable pattern for future responsive rendering work (e.g., if we need to support different DPIs in Phase 6.1).

3. **The "measure at call site" pattern** — `main.js` measures the container and passes it down, rather than having `panels.js` query the DOM. This keeps rendering pure and testable.

## Questions for Future Phases

1. Should panel re-rendering on window resize be part of Phase 2 (zoom/pan) or a separate enhancement?

2. At what viewport width do fixed font sizes become a problem? (Empirical testing suggests <400px, but real user data would help.)

3. Should the circuit map also get dynamic viewBox scaling, or is the current CSS-based scaling sufficient?

---

**No blockers or surprises that affect Phase 0.5.** The codebase is ready for the walking skeleton implementation.
