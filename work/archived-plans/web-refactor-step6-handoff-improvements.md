# Web Refactor — Step 6 Handoff: Suggested Improvements

Based on issues discovered during the bug-fix session (2026-05-13), the following improvements should be made to `web-refactor-step6-handoff.md`:

---

## 1. Add "Known Issues / Gotchas" Section

**New section to add after "Current State":**

```markdown
---

## Known Issues / Gotchas

### ES Modules Require HTTP(S)

`web/compare.html` uses `<script type="module" src="js/main.js">`. **This does not work via `file://`** due to browser CORS restrictions on ES modules.

**Symptoms:**
- Console errors: "Cross-Origin Request Blocked" or "Module source URI is not allowed"
- Button clicks do nothing (JavaScript never loaded)
- Page renders but is non-functional

**Solutions:**
1. Use `dist/compare.html` — bundled single file, works via `file://`
2. Serve `web/` via HTTP: `python3 -m http.server 8000` or any static server

**Test runs must use HTTP** — the test server (`scripts/lib/test-server.js`) handles this correctly.

### Event Handler Scope Rules

Event handlers (e.g., `plotArea.addEventListener('mouseup', ...)`) **cannot access local variables** from functions like `renderAll()`. They must use:
- Global/module-scope variables (e.g., `state.maxDist`, `currentZoomRange`)
- Properties on `state` object for values that change per-render

**Common mistake:** Using `maxDist` (local to `renderAll`) in event handlers → `undefined` at runtime.

**Correct pattern:**
```javascript
// ❌ Wrong - maxDist is local to renderAll()
plotArea.addEventListener('mouseup', e => {
  const d2 = Math.min(state.maxDist, ...);  // OK
  persistZoom(currentZoomRange, maxDist);   // undefined!
});

// ✅ Correct - use state.maxDist
plotArea.addEventListener('mouseup', e => {
  const d2 = Math.min(state.maxDist, ...);
  persistZoom(currentZoomRange, state.maxDist);  // OK
});
```

---
```

---

## 2. Update "Functions to Extract" Table

**Add a "Scope Notes" column** to flag functions used in event handlers:

| Function | Lines | Description | Dependencies | Scope Notes |
|----------|-------|-------------|--------------|-------------|
| `resample` | 259–277 | Distance-aligned resampler | `interpAt` | Called from `renderAll` — OK to extract |
| `computeDeltaT` | 279–291 | Session vs ref lap time diff | None | Pure function — OK to extract |
| `computeKeepIndices` | 293–311 | Δt overlap window | None | Pure function — OK to extract |
| ... | ... | ... | ... | ... |

---

## 3. Add "Extraction Guidelines" Section

**New section before "Acceptance Criteria":**

```markdown
---

## Extraction Guidelines

### Safe to Extract
- **Pure functions** with no DOM access or global state
- Functions that only use their parameters and imported constants
- Helper functions called only from other extractable functions

### Keep in main.js
- **Event handlers** (mouse, keyboard, click listeners)
- Functions that access DOM elements directly
- Functions that read/write `state` object properties
- Functions that use `currentZoomRange`, `currentSessionBins`, etc.

### Watch Out For
- Functions called from event handlers must not rely on closure over local variables
- If a function uses `maxDist`, `zoomRange`, etc., ensure these are on `state` or passed as parameters
- Test extraction by running `npm run build` — esbuild will catch import errors

---
```

---

## 4. Update Test Status Section

**Add note about test execution:**

```markdown
### Test Status
```
M5:     25/25 ✔
M6:     26/26 ✔
F1F2:   13/13 ✔
Extras: 17/17 ✔
────────────────
Total:  81/81 passing
```

**Note:** Tests run via HTTP server (`scripts/lib/test-server.js`). Do not test by opening HTML files directly in browser.
```

---

## 5. Add "Validation Checklist" Before Acceptance Criteria

```markdown
---

## Validation Checklist

Before considering Step 6 complete:

- [ ] Run `npm run build` — verify no esbuild errors
- [ ] Run `npm test` — all 81 assertions must pass
- [ ] Open `dist/compare.html` in browser — verify zoom drag works
- [ ] Check console for "undefined" errors (scope issues)
- [ ] Verify file picker button works (when served via HTTP)

**Quick smoke test:**
```bash
npm run build && npm test
open dist/compare.html  # Manual verification
```

---
```

---

## 6. Add Debug Tips Section

```markdown
---

## Debug Tips

### Scope Issues in Event Handlers
If zoom/click interactions stop working after refactoring:
1. Check browser console for `undefined` errors
2. Search event handlers for variables that should be `state.xxx`
3. Common culprits: `maxDist`, `zoomRange`, `currentRenderParams`

### Module Import Errors
If `npm run build` fails with import errors:
1. Verify all exports in `pipeline.js` are named correctly
2. Check import statement in `main.js` matches exports exactly
3. Ensure no circular dependencies (pipeline.js should not import main.js)

### Testing File Picker
The "+ Load parquet" button requires HTTP:
```bash
# Option 1: Use dist/ (bundled, works via file://)
open dist/compare.html

# Option 2: Serve web/ via HTTP
python3 -m http.server 8000
# Then open http://localhost:8000
```

---
```

---

## 7. Update "Next Steps After Step 6"

**Add cautionary note:**

```markdown
## Next Steps After Step 6

**Step 7 candidates** (TBD):
- Extract `panels.js` — `renderPanel`, `renderDtPanel`, panel-specific SVG logic
- Extract `circuitMap.js` — `renderCircuitMap`, `renderHeatmapSegments`, `renderMapLegend`, `updateZoomArc`
- Extract `ui.js` — picker rebuild, compare button, drag-and-drop handlers

**Caution:** Event handlers in `ui.js` must use `state` object, not closure over local variables. Review the "Known Issues / Gotchas" section before extracting.

---
```

---

## Summary of Changes

| Section | Change | Reason |
|---------|--------|--------|
| New: Known Issues | Document file:// and scope issues | Prevent repeat of bugs from this session |
| Functions table | Add "Scope Notes" column | Flag functions used in event handlers |
| New: Guidelines | Define safe extraction patterns | Help future refactors avoid scope traps |
| Test Status | Note HTTP requirement | Clarify why tests use test-server |
| New: Validation | Add smoke test checklist | Catch issues before committing |
| New: Debug Tips | Troubleshooting guide | Faster debugging of common issues |
| Next Steps | Add cautionary note | Warn about event handler scope in future extractions |

These improvements encode the lessons learned from fixing the zoom bug (scope issue) and investigating the file picker "bug" (ES modules require HTTP) into the handoff document for future refactors.
