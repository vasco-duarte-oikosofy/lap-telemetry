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
