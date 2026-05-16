# Slice 04 — Playwright acceptance test for auto-zoom

## Goal

Write a Playwright test that validates the auto-zoom behaviour end-to-end.
The test exercises the feature by simulating chart-zoom interactions and
checking that the map zooms, pans, and resets correctly. The test should
also verify that existing features (linked highlight, zoom/pan reset) are
not broken by the new feature.

**Important:** Read [`docs/TESTING_LESSONS.md`](../../../docs/TESTING_LESSONS.md)
and [`work/completed/parallel-test-runner/FUTURE_IMPROVEMENT_IDEAS.md`](../../completed/parallel-test-runner/FUTURE_IMPROVEMENT_IDEAS.md)
before writing any tests. Follow the patterns and lessons documented there.

## Context

### Known bugs to validate

Before writing the test, read [`BUGS.md`](../BUGS.md) for the full list of
bugs found during implementation. The test must exercise the scenarios that
exposed these bugs. Specifically, the test must verify:

1. **Bug 5 fix**: Double-click reset works when `mapAutoZoom` is on.
2. **Bug 6 fix**: Enabling `mapAutoZoom` with nothing selected does NOT
   move the map.
3. **Bug 7 fix**: Auto-zoom consistently targets the correct portion of
   the track.
4. **Bug 8 fix**: Long highlighted portions (e.g., T1 at Fuji) show the
   full highlighted section.
5. **Bug 9 fix**: The map ZOOMS into the segment, not just pans.

### How auto-zoom works

- `mapAutoZoom` (feature flag, default `false`) must be enabled alongside
  `mapLinkedHighlight` for auto-zoom to take effect.
- When a chart zoom range is present (`currentZoomRange`), the map
  computes segment bounds via `computeSegmentBounds(lapA, range)`.
- The padded bounds are passed as `autoZoomBounds` to
  `renderWalkingSkeleton`, which uses them in `fitToView` to zoom in.
- When the zoom range is cleared (full-track), the map returns to
  full-track view.
- `window.__mapZoomPanState` exposes `{ scale, tx, ty }` — when auto-zoomed,
  `scale` remains 1 but the view is zoomed because `fitToView` uses the
  segment bounds instead of the full-track bounds.
- **Important**: the auto-zoom is purely a rendering-level change (different
  bounds passed to `fitToView`), NOT a scale change. The `scale` in
  `__mapZoomPanState` stays at 1. To detect auto-zoom, check the canvas
  transform or the bounding box of the visible track segment, NOT the scale.

### Debug hooks available

- `window.__features` — read feature flags
- `window.__setFeatureFlag(name, value)` — toggle feature flags
- `window.__setFeatureFlagMenuEnabled(enabled)` — show/hide feature-flag menu
- `window.__mapZoomPanState` — `{ scale, tx, ty }` for map zoom state
- `window.__getSessionKeys()` — get loaded session keys
- `window.__setZoomRange(start, end)` — **needs to be added** (see below)

### Why we need `__setZoomRange`

Currently there is no way to programmatically set the chart zoom range from
a Playwright test. Drag-selecting on a panel is fragile and
viewport-dependent (see Testing Lessons L1 and L3). Adding a debug hook
`window.__setZoomRange(start, end)` allows the test to set a precise zoom
range and verify the auto-zoom behaviour deterministically.

Add this hook in `product/web/js/debugHooks.js` (or via `main.js` if that's
where `currentZoomRange` is accessible). The hook should:

- Set `currentZoomRange` to `{ start, end }`
- Call `renderAll()` to trigger a re-render
- Return the new range

Similarly, add `window.__clearZoomRange()` that resets to full-track and
calls `renderAll()`.

### Session file

Use the Barcelona session file:
`dev/sessions/session_20260510T074144Z_circuit-de-barcelona_lmu.parquet`

This session has 6 laps with clear track geometry that makes auto-zoom
validation straightforward.

## Steps

1. **Add `window.__setZoomRange(start, end)` and `window.__clearZoomRange()`
   debug hooks.** These set `currentZoomRange` and call `renderAll()`. This
   is the most reliable way to exercise auto-zoom in tests — avoids
   fragile drag-select interactions (see Testing Lessons L1, L3).

2. **Write `dev/scripts/test_f16_auto_zoom_acceptance.js`.** The test must
   use `// @parallel true` and follow the existing Playwright test pattern
   (start server, launch browser, load session, assert, tear down).

3. **Test scenarios** (each with clear `[PASS]`/`[FAIL]` assertions):

   **SCENARIO 1: Default state — map shows full track**
   - Load session, enable `mapLinkedHighlight` and `mapAutoZoom`.
   - Without any chart zoom, verify the map canvas renders the full track
     (no auto-zoom). Check that `window.__mapZoomPanState.scale` is 1.

   **SCENARIO 2: Auto-zoom activates when chart zoom is set**
   - Use `__setZoomRange` to set a zoom range (e.g., `{ start: 300, end: 700 }`).
   - Verify the canvas renders a zoomed-in view. The way to detect this:
     sample canvas pixels at the edges vs center. If auto-zoom is working,
     the track should occupy a larger portion of the canvas compared to
     the full-track view.
   - Alternatively, use `window.__features.mapAutoZoom` and check that
     `computeSegmentBounds` returns non-null for the range.

   **SCENARIO 3: Auto-zoom resets when chart zoom is cleared**
   - After SCENARIO 2, call `__clearZoomRange()`.
   - Verify the map returns to full-track view (same as SCENARIO 1).

   **SCENARIO 4: Enabling mapAutoZoom with nothing selected doesn't move the map**
   - Load session, enable `mapLinkedHighlight`, do NOT enable `mapAutoZoom`.
   - Get a reference: screenshot or canvas pixel data.
   - Enable `mapAutoZoom`.
   - Verify the map has NOT moved (same transform, same view).

   **SCENARIO 5: computeSegmentBounds consistency**
   - Call `__setZoomRange(300, 700)`.
   - Use `window.__computeSegmentBounds` (add this debug hook wrapping
     `computeSegmentBounds`) or just check that the auto-zoomed view
     centers on the correct portion of the track.
   - Call `__setZoomRange(300, 700)` again.
   - Verify the result is identical (non-random).

   **SCENARIO 6: mapAutoZoom and mapZoomPan coexist**
   - Enable both `mapAutoZoom` and `mapZoomPan`.
   - Set a zoom range.
   - Verify auto-zoom activates (zoomed-in view).
   - Double-click the map canvas to reset.
   - Verify the map returns to auto-zoomed view (not full-track) because
     the chart range is still set. Double-click resets user pan/zoom but
     auto-zoom re-applies on next render.

   **SCENARIO 7: Screenshot artifacts**
   - Take a screenshot after each key state (full-track, zoomed-in,
     zoom-cleared) for manual review.

4. **Run `bash scripts/test-summary.sh`.** Must pass with the new test
   included.

5. **Register the test in `package.json`** test script chain.

6. **Commit.**

## Acceptance

- `window.__setZoomRange(start, end)` and `window.__clearZoomRange()` debug
  hooks exist and work.
- `test_f16_auto_zoom_acceptance.js` passes with ≥ 7 assertions.
- Full suite passes: `ALL PASS`.
- Build succeeds: `npm run build`.

## Testing lessons to apply

From `docs/TESTING_LESSONS.md`:

- **L0**: Every assertion prints `[PASS]` or `[FAIL]`.
- **L1**: Use `element.hover({ position })` instead of `page.mouse.move()`
  with absolute coordinates.
- **L2**: Re-acquire elements after any re-render.
- **L3**: Each test section scrolls into view independently.
- **L4**: Wait for data state (`window.__getSessionKeys`), not just DOM.
- **L7**: Screenshots are artifacts — verify file exists and is non-empty.
- **L9**: Assert the visible renderer (canvas), not implementation details
  (SVG vs canvas).

From `FUTURE_IMPROVEMENT_IDEAS.md`:

- **Idea #2**: Use `page.goto(url, { waitUntil: 'domcontentloaded' })`
  then `page.waitForFunction(() => window.__features)` instead of the
  default `load` wait. Saves ~0.5s.
- **Idea #5**: Batch `page.evaluate()` calls where possible. Instead of
  multiple round-trips, return all needed values in one object.

## Non-goals

- Do not fix the open bugs (5–9). This test validates current behaviour
  and will be updated as bugs are fixed.
- Do not change the auto-zoom implementation.
- Do not add visual regression testing (pixel diff).
- Do not use drag-select to simulate chart zoom (fragile per L1/L3);
  use `__setZoomRange` instead.