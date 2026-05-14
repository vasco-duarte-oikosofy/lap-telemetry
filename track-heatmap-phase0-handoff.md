# Track Heatmap — Phase 0 Handoff

**Date:** 2026-05-13  
**Status:** Ready to start · All 81 tests passing · `main.js` at 437 lines  
**Feature Flag:** `features.mapLayoutPromoted` (default OFF)

---

## Spec Reference

This handoff implements **Phase 0** of the [track-heatmap-spec.md](track-heatmap-spec.md).

Read the full spec first — especially the **XP working agreements** (§1–10) and **file architecture constraints**. Key principles:

1. **One subphase at a time** — do not bundle Phase 0 with Phase 0.1 or Phase 0.5
2. **Test-first** — write failing tests before code
3. **YAGNI** — do not add abstractions or "while I'm here" cleanups
4. **Stop at green** — when acceptance passes, commit and move on

---

## Goal

**Layout change only.** Promote the circuit map to the top of the comparison page and give it 50% of the page width. No renderer changes.

---

## Current State

### File Structure
```
web/compare.html          — Single-page app (no build step, ESM imports from CDN)
web/css/styles.css        — All styles inlined into dist/compare.html at build time
web/js/main.js            — 437 lines (HARD CEILING — do not exceed)
web/js/circuitMap.js      — 168 lines — current map renderer
web/js/ui.js              — 327 lines — UI interaction
web/js/pickers.js         — 111 lines — picker/session-list DOM
web/js/cursor.js          — 232 lines — cursor/tooltip/zoom
web/js/panels.js          — 283 lines — telemetry panel rendering
web/js/pipeline.js        — 432 lines — data pipeline
web/js/dataTransforms.js  — 88 lines  — pure data parsing
web/js/utils.js           — 129 lines — helpers
web/js/appState.js        — 59 lines  — global state
web/js/constants.js       — 6 lines   — SVG constants
```

### Current Layout
The circuit map is rendered in a sidebar to the right of the plot panels:
- Plot area: ~70% width
- Map sidebar: fixed 250px width (~28%)
- Map is positioned **after** the plot stack in DOM order

### Key Files to Modify
1. **`web/compare.html`** — HTML structure, CSS layout
2. **`web/css/styles.css`** — if separate CSS file exists (check if inlined at build)

---

## Tasks

### 1. Restructure HTML

Move the map container to be the **first** element in the main content area, before the plot panels.

Current structure (approximate):
```html
<div id="plot-area">...</div>
<div id="circuit-map-sidebar">...</div>
```

New structure:
```html
<div id="map-container">...</div>
<div id="plot-area">...</div>
```

### 2. Update CSS Layout

**Desktop (≥1024px):**
- Map container: 50% of page content width
- Remaining content (plot area + loader panel): 50%
- Map height: `min(60vh, 720px)` with floor of 420px

**Mobile (<1024px):**
- Layout stacks vertically
- Map full-width on top
- Plot area + loader below
- Map height formula unchanged

### 3. Feature Flag

Wrap the new layout behind `features.mapLayoutPromoted`. When OFF, render the original layout. When ON, render the new promoted layout.

Pattern from existing codebase (check how other features are flagged — likely a simple CSS class or JS toggle).

---

## Acceptance Criteria (Executable Tests)

Add tests to a new file `scripts/test_phase0.js` or extend existing test harness.

### Test 1: Desktop viewport dimensions
```javascript
// At 1440×900 viewport
// Map bounding box should be 700–740px wide AND 700–740px tall
```

### Test 2: Mobile viewport stacking
```javascript
// At 768×1024 viewport  
// Map should be full-width (≥720px) and stacked above plot area
```

### Test 3: Render test
```javascript
// Existing circuit map renderer mounts and paints without errors
// Pixel-diff allowed to differ in scale only, not content
```

### Test 4: Feature flag toggle
```javascript
// With flag OFF: original layout renders
// With flag ON: new layout renders
```

---

## Implementation Notes

### Do NOT Change
- The map renderer (`circuitMap.js`) — no behavior changes
- Panel rendering (`panels.js`) — no layout logic moves
- Any zoom/pan handlers — those are Phase 2
- Color ramps, ribbons, heatmaps — those are Phase 1a+

### CSS Guidelines
- Use CSS Grid or Flexbox for the two-column layout
- Respect the height formula: `height: min(60vh, 720px)` with `min-height: 420px`
- Ensure the map canvas fills its container (no hardcoded canvas sizes)
- Test at breakpoints: 320px, 768px, 1024px, 1440px, 2000px

### Feature Flag Pattern
Check existing patterns in the codebase:
- `LAP_COLOUR_LS_KEY` in `utils.js` for localStorage persistence
- `PANEL_ORDER_LS_KEY` in `appState.js` for persisted state
- Consider similar pattern: `MAP_LAYOUT_LS_KEY` for user preference

---

## Test Plan

### Before Starting
1. Run `npm test` — verify all 81 tests pass
2. Run `npm run build` — verify clean build
3. Open `dist/compare.html` — verify current layout works

### During Implementation
1. Write failing tests first (Test 1–4 above)
2. Implement layout changes
3. Run tests after each small change
4. Keep commits small and green

### Before Merging
1. All 81 existing tests must pass
2. All 4 new Phase 0 tests must pass
3. Manual verification in browser at multiple viewport sizes
4. Verify feature flag toggle works
5. Verify no console errors

---

## Definition of Done

- [ ] Tests written and passing (81 existing + 4 new)
- [ ] Feature flag implemented and default OFF
- [ ] Desktop layout: map at 50% width, top of page
- [ ] Mobile layout: map full-width, stacked
- [ ] Map height respects `min(60vh, 720px)` with 420px floor
- [ ] No renderer changes (pixel-diff at original scale is identical)
- [ ] No `main.js` changes (or minimal wiring only)
- [ ] No file exceeds 437 lines
- [ ] Commit messages explain *why*, not just *what*
- [ ] Handoff notes document the layout decision (50% width rationale)

---

## Out of Scope

These are **not** part of Phase 0. Do not touch them:

- ❌ Renderer responsiveness (Phase 0.1)
- ❌ Two-lap rendering (Phase 0.5)
- ❌ Heatmap ribbons (Phase 1a)
- ❌ Zoom/pan (Phase 2)
- ❌ Legend (Phase 3)
- ❌ Hover readout (Phase 4)
- ❌ Linked highlight band (Phase 5a)

---

## Next Steps After Phase 0

Once Phase 0 is complete on `main`:

1. **Decision gate:** Look at the result. If 50% width feels right, continue. If map still feels small, bump to 60% or 66% (one-line CSS change) before Phase 0.1.

2. **Phase 0.1:** Audit renderer for hardcoded dimensions, replace with container-derived values (pure refactor, no visible change).

3. **Phase 0.5:** Walking skeleton — two laps as 1px polylines on same canvas.

---

## References

- [track-heatmap-spec.md](track-heatmap-spec.md) — Full specification
- [DESIGN.md](DESIGN.md) — Architecture, file format, milestone plan
- [RENDER_DESIGN.md](RENDER_DESIGN.md) — Rendering architecture
- [NEXT_STEPS.md](NEXT_STEPS.md) — Future improvements backlog
