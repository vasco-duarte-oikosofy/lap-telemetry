# F16 Auto-Zoom — Playwright Test Performance Improvements — Learnings

## What Surprised Me

1. **Combined `waitForFunction()` caused timeout issues** — When I tried to combine all three readiness checks (session keys, panels, zoom range) into a single `waitForFunction()`, the test timed out. The issue was that `window.__getSessionKeys()` was being called before the session data was fully loaded. **Lesson**: Keep the session keys wait separate since it's the prerequisite for everything else.

2. **Batching canvas pixel sampling is straightforward** — I expected batching canvas analysis with state reads to be complex, but it's simply a matter of wrapping the canvas sampling logic inside the same `page.evaluate()` that reads other state. The canvas context is available in the page context, so no special handling needed.

3. **Performance gains exceeded estimates** — The handoff estimated 2-3s savings; we achieved ~3.8s savings (57-70% reduction per test). The biggest win was replacing `waitForTimeout(300)` calls — tests now wait only as long as needed (typically 10-50ms instead of 300ms).

## Implementation Patterns Worth Remembering

### Batching pattern for canvas + state:
```javascript
const state = await page.evaluate(() => {
  const canvas = document.getElementById('track-heatmap-canvas');
  if (!canvas) return null;
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  const pixels = [];
  for (let py = 0; py < 10; py++) {
    for (let px = 0; px < 10; px++) {
      const x = Math.floor(w * (px + 1) / 11);
      const y = Math.floor(h * (py + 1) / 11);
      const d = ctx.getImageData(x, y, 1, 1).data;
      pixels.push({ r: d[0], g: d[1], b: d[2], a: d[3] });
    }
  }
  return {
    zoom: window.__getZoomRange(),
    mapState: window.__mapZoomPanState,
    canvas: { w, h, pixels },
  };
});
// Now use state.zoom, state.mapState, state.canvas
```

### waitForFunction pattern for state transitions:
```javascript
await page.evaluate(() => window.__setZoomRange(3000, 4000));
await page.waitForFunction(
  ([start, end]) => {
    const z = window.__getZoomRange();
    return z && z.start === start && z.end === end;
  },
  [3000, 4000],
  { timeout: 2000 }
);
```

## What the Next Agent Needs to Know

1. **Test timing is now non-deterministic** — Since we replaced fixed delays with state-based waits, test runtime varies based on how fast the app responds. This is good (tests are faster) but means timing comparisons should use averages, not single runs.

2. **The `loadSession()` pattern** — Keep the session keys wait separate from the combined panels+zoom wait. This ordering matters because session data must be loaded before panels can render.

3. **Deferred: shared browser context** — Idea #6 (shared browser context) was not implemented. It would require a test harness refactor to pass browser instances to tests. Consider this when adding more Playwright tests to the suite.

## Mistakes Made (and Fixed)

1. **First attempt at combined readiness check failed** — I initially tried to combine all three waits (keys, panels, zoom) into one `waitForFunction()`. This caused timeouts because the session keys check was being evaluated before the session was uploaded. **Fix**: Keep the keys wait separate, then combine panels+zoom.

2. **Forgot to update assertion count** — The auto-zoom test went from 20 to 22 assertions after adding null checks for batched state reads. Make sure to update any documentation that references assertion counts.
