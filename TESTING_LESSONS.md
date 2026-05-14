# Testing Lessons — Playwright / Headless Chromium

Read this file before writing a new test or debugging a failing one.

---

## L1. Use `.hover()` with relative positions, not `mouse.move()` with absolute coordinates

**Problem.** `page.mouse.move(box.x + box.width/2, box.y + box.height/2)` uses
absolute viewport coordinates. If the target element is below the viewport fold
(y > 720 px in Playwright's default 1280x720 viewport), headless Chromium
silently drops the event — no `mousemove` fires on any DOM element.

**Solution.** Use `element.hover({ position: { x, y } })` with element-relative
coordinates. `.hover()` auto-scrolls the element into view before dispatching.

```javascript
// Fragile: silent no-op when element is below the viewport
const box = await panelSvg.boundingBox();
await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);

// Robust: auto-scrolls, then dispatches at element-relative position
await panelSvg.hover({ position: { x: box.width / 2, y: box.height / 2 } });
```

---

## L2. Re-acquire elements after any re-render

**Problem.** `renderAll()` rebuilds the DOM via `panelsDiv.innerHTML = ''`.
Any element handle grabbed before a re-render (zoom, reset, lap change) is
now a detached node — `.boundingBox()` may return stale coordinates or null.

**Solution.** Re-query the element immediately before each interaction.

```javascript
// Fragile: panelSvg was grabbed before the zoom re-render
const panelBox = await panelSvg.boundingBox();  // stale / detached

// Robust: fresh handle after re-render
const freshPanel = await page.$('.panel-svg');
const box = await freshPanel.boundingBox();
```

---

## L3. Each test must own its scroll position

**Problem.** Tests that use `.hover()` (which scrolls) create a hidden
dependency: later tests pass only because an earlier test scrolled the page
into the right position. Reordering or skipping tests causes failures.

**Solution.** Every test section that interacts with mouse events on a
potentially-below-fold element must independently scroll into view via its
own `.hover()` call. Never assume the page is already scrolled.

```javascript
// Each section: re-acquire, scroll into view, interact
const panel = await page.$('.panel-svg');
await panel.hover({ position: { x: 1, y: 1 } });   // scroll into view
const box = await panel.boundingBox();                // now in-viewport
await page.mouse.move(box.x + box.width * 0.2, ...); // safe
```

---

## L4. Wait for data state, not just DOM elements

**Problem.** Waiting for a `<polyline>` to appear doesn't guarantee
`currentSessionBins` is populated. The element exists but the data
driving the tooltip / cursor dot isn't ready yet.

**Solution.** Wait for the actual data state:

```javascript
await page.waitForFunction(() => {
  return window.__getSessionKeys && window.__getSessionKeys().length > 0;
}, { timeout: 5000 });
```

---

## L5. Module-scoped variables aren't accessible in `page.evaluate()`

**Problem.** `currentSessionBins` is a `let` at module scope in `main.js`.
`page.evaluate(() => currentSessionBins)` throws `ReferenceError` because
Playwright evaluates in the page's global scope, not the module scope.

**Solution.** Expose debug helpers on `window` for test access:

```javascript
// main.js
window.__debugGetBins = () => ({ currentSessionBins, currentRefBins });

// test
const state = await page.evaluate(() => window.__debugGetBins());
```

---

## L6. Add debug logging before asserting

**Problem.** When a test fails, "FAIL: tooltip displayed" doesn't tell you
whether the tooltip was invisible, empty, or had wrong content.

**Solution.** Log state before the assertion:

```javascript
const tooltipText = await page.$eval('#tooltip', el => el.textContent);
console.log(`  Tooltip visible: ${tooltipVisible}`);
console.log(`  Tooltip text: ${tooltipText.slice(0, 200)}`);
assert(tooltipText.includes('dist:'), ...);
```

This turns "test failed" into "tooltip is visible but textContent is empty
string", which points directly at the root cause.

---

## L7. Screenshots are artifacts unless compared or asserted

**Problem.** Saving a screenshot can look like coverage, but it does not fail
the test unless the file is compared or at least checked. A scenario named
"pixel diff" that only writes a PNG gives false confidence.

**Solution.** Either use a real visual assertion/diff, or clearly label the
PNG as a manual artifact and assert the layout invariants in code. If writing
artifacts, verify the file was created and is non-empty.

```javascript
await page.screenshot({ path: shotPath });
const size = fs.statSync(shotPath).size;
assert(size > 0, 'screenshot artifact written', `${size} bytes`);
```

---

## L8. Be explicit about viewport width vs content/container width

**Problem.** A responsive test may say it is testing a 320px container while
actually setting a 420px viewport and relying on body padding/margins. That can
hide or invent overflow failures.

**Solution.** Define which width is under test. If testing content width, set
the viewport from the desired content width plus measured horizontal padding,
then assert the measured content width before checking layout.

```javascript
const paddingX = await page.evaluate(() => {
  const cs = getComputedStyle(document.body);
  return parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
});
await page.setViewportSize({ width: targetContentWidth + paddingX, height: 1200 });
```

---

## L9. Assert the visible renderer, not a hard-coded implementation element

**Problem.** A feature can switch between SVG and canvas rendering. Asserting
that `#circuit-map-svg` has a non-zero box fails when the canvas renderer is
visible, even though the map is correctly rendered.

**Solution.** Assert the visible rendering surface or accept all supported
surfaces, then keep implementation-specific checks limited to what they really
prove.

```javascript
const size = await page.evaluate(() => {
  const svg = document.getElementById('circuit-map-svg').getBoundingClientRect();
  const canvas = document.getElementById('track-heatmap-canvas').getBoundingClientRect();
  return Math.max(svg.width, canvas.width);
});
assert(size > 0, 'map renderer has visible width');
```
