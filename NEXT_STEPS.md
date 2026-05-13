# lap-telemetry — Next Steps & Future Improvements

**Date:** 2026-05-13  
**Status:** Web refactor complete (Steps 9–12 shipped) · `main.js` reduced from 1869 → 437 lines (-77%)

---

## Module Structure (Complete)

| File | Lines | Role |
|------|-------|------|
| `appState.js` | 59 | Global state (store, panelOrder, zoom, map mode) |
| `constants.js` | 6 | Shared SVG layout constants |
| `cursor.js` | 232 | Cursor/tooltip/zoom interaction (Step 12) |
| `dataTransforms.js` | 88 | Pure data parsing (Step 11) |
| `pickers.js` | 111 | Picker/session-list DOM projection (Step 10) |
| `circuitMap.js` | 168 | Circuit map rendering |
| `panels.js` | 283 | Telemetry panel rendering |
| `pipeline.js` | 432 | Data loading/processing |
| `ui.js` | 327 | UI interaction (file loading, event handlers) |
| `utils.js` | 129 | Helpers, formatting, persistence |
| `main.js` | 437 | App entry point, `renderAll` orchestration, debug hooks |

**Total:** 2272 lines · **All 81 tests passing**

---

## Potential Further Refactoring (Optional)

### 1. Extract `PANEL_DEFS` to `panelConfig.js` (~50 lines)

**What.** Move the panel definition array from `main.js` to a dedicated config module, potentially alongside `panels.js`.

**Why.** `PANEL_DEFS` is pure configuration data — no logic, no state. Extracting it would:
- Reduce `main.js` to ~390 lines
- Co-locate panel schema with panel rendering logic
- Make it easier to add/remove/reorder panels without touching `renderAll`

**Pattern.**
```javascript
// panelConfig.js
export const PANEL_DEFS = [ ... ];
export const DEFAULT_PANEL_ORDER = [ ... ]; // could also move from appState.js

// panels.js or main.js
import { PANEL_DEFS } from './panelConfig.js';
```

**Effort:** ~15 lines (export + re-import)

---

### 2. Extract Debug Hooks to `debug.js` (~100 lines)

**What.** Move test-only exports (`__getSessionKeys`, `__resamplerDebug`, `__dtDebug`, `__dtDebugOverlap`) to a dedicated debug module.

**Why.** These functions are only used by Playwright tests and local debugging. Extracting them would:
- Reduce `main.js` to ~340 lines
- Make the test harness more explicit
- Allow stripping debug exports from production builds (esbuild tree-shaking)

**Pattern.**
```javascript
// debug.js
import { store } from './appState.js';
import { resample, smoothLapTime, computeDeltaT, ... } from './pipeline.js';

export function getSessionKeys() { ... }
export function resamplerDebug(storeKeyStr, segIdx) { ... }
export function dtDebug(sKey, sSeg, rKey, rSeg) { ... }
export function dtDebugOverlap(sKey, sSeg, rKey, rSeg) { ... }

// main.js
import { getSessionKeys, resamplerDebug, dtDebug, dtDebugOverlap } from './debug.js';
window.__getSessionKeys = getSessionKeys;
window.__resamplerDebug = resamplerDebug;
window.__dtDebug = dtDebug;
window.__dtDebugOverlap = dtDebugOverlap;
```

**Effort:** ~20 lines (move + re-export)

---

### 3. Split `renderAll()` (Not Recommended)

**What.** Break the 200-line `renderAll()` function into smaller sub-functions.

**Why Not.** `renderAll()` is the core orchestration logic that ties the entire app together. It:
- Reads from store entries
- Computes keep indices and resampling
- Builds panel HTML
- Renders circuit map
- Updates legend and state

Splitting it would create artificial boundaries and hurt clarity more than help. The function is well-commented and follows a clear linear flow. Keep as-is.

---

## Future Fixes — UX Backlog (from DESIGN.md §13)

### U2. Circuit map needs more pixels for brake/throttle overlays

**Symptom.** The sidebar map is fixed at 250 px. When the user toggles brake or throttle overlay, the colour-coded track ribbon is too small to read individual braking zones.

**Fix direction.** Enlarge the map when an overlay is active (or unconditionally):
- (a) Bump sidebar to ~400 px fixed, shrink plot stack proportionally
- (b) Make map width user-resizable via draggable column splitter with `localStorage` persistence
- (c) Add "expand map" toggle that swaps map/plot proportions for analysis sessions

**Scope.** `web/compare.html` layout + `renderCircuitMap` viewBox scaling. No schema or recorder changes.

**Priority:** Medium — affects track-overlay analysis workflows.

---

### U3. Throttle panel shows wrong colour and only one trace

**Symptom.** The Throttle panel renders a single green trace instead of two traces (session + reference) coloured with lap identity colours (`--session` / `--ref`) and solid/dashed line style.

**Fix direction.** Audit Throttle (and Brake) channel definitions in `PANEL_DEFS`. Both should declare:
- One `trace: 'session'` in `var(--session)` solid
- One `trace: 'ref'` in `var(--ref)` dashed

Remove any channel-specific green/red colour overrides from earlier designs.

**Scope.** `PANEL_DEFS` in `web/js/main.js`. No schema or recorder changes.

**Priority:** High — visual regression affecting core comparison feature.

---

### U4. Tooltip speed values should be coloured by lap identity

**Symptom.** The cursor tooltip shows both laps' speed on the same line in plain text (e.g., `speed: 248.3 / 263.5 km/h`). No visual cue which value belongs to which lap.

**Fix direction.** Render each speed value in its lap colour:
```javascript
tooltip.innerHTML = `
  dist: ${binIdx} m<br>
  speed: <span style="color:var(--session)">${sSpeed.toFixed(1)}</span> /
         <span style="color:var(--ref)">${rSpeed?.toFixed(1) ?? '—'}</span> km/h<br>
  ...
`;
```

Apply same colouring to throttle, brake, and other dual-value fields. Sanitise user-derived strings before `innerHTML` to avoid XSS.

**Scope.** Tooltip rendering in `updateCursorPosition` in `web/js/cursor.js`. No schema or recorder changes.

**Priority:** Medium — improves readability, not blocking.

---

### U5. Audit all panels for consistent colour/line-style

**Symptom.** Reported inconsistency: some panels (slip angle confirmed) may not apply `--session` / `--ref` colours and solid/dashed trace convention.

**Fix direction.** Walk every entry in `PANEL_DEFS` and confirm:
- `trace: 'session'` → `var(--session)` + solid
- `trace: 'ref'` → `var(--ref)` + dashed

ABS and TC panels are session-only by design (single solid trace in channel colour is correct for binary panels).

Add regression test confirming channel colour/dash for Speed, Throttle, Brake, Slip, and Δt.

**Scope.** `PANEL_DEFS` in `web/js/main.js`; optionally extend `test_f8f9f10f11.js`.

**Priority:** Medium — visual consistency across panels.

---

## Known Issues — Recorder/Reader (from DESIGN.md §10)

### O1/O2. Sector lookup mid-update / off-by-one ✅ Resolved M4

**Status:** Fixed in `7695698`. Reader now walks up to 25 frames into the next segment until both `mLastSector1 > 0` and `cum_s2 > s1`, capturing settled values instead of catching SHM mid-update.

---

### O3. First-compare UI freeze (~100–300 ms)

**Symptom.** After loading a parquet, the first time both lap pickers are populated and `renderAll` fires, the page is unresponsive for ~100 ms on fast hardware and ~200–300 ms on slower machines.

**Cause.** Profiled on a ~25k row session: `renderAll` does ~31 ms of resampling (16 channels × 2 traces) and ~70 ms of SVG string-building + `innerHTML` parse + paint, all in one synchronous JS block.

**Remediations (if it becomes a friction point):**
1. **Cache resampled bins** per `(storeKey, segIdx, col)` so repeat picks are instant (~50 lines)
2. **Async pre-resample** after file load with "warming…" badge, chunked with `await yield()` (~80 lines)
3. **Yield between panels** inside `renderAll` so panels appear progressively (~20 lines)

**Priority:** Low — workflow completes, freeze is short. Revisit if users report it as blocking.

---

## Future Features — Not Yet Scheduled

### F12. Persistent lap selection

**What.** Persist the selected lap pair (`session-picker` + `ref-picker` values) in `localStorage` so reloading the page restores the previous comparison.

**Pattern.** Same as zoom (`ZOOM_LS_KEY`) and panel order (`PANEL_ORDER_LS_KEY`).

**Scope.** `web/js/ui.js` picker change handlers + `web/js/appState.js` persistence helpers.

---

### F13. Export comparison as PNG/SVG

**What.** Add a "Download" button that exports the current panel stack + circuit map as a single PNG or SVG file for sharing or archival.

**Implementation sketch.** Use `canvas.toBlob()` for PNG (rasterize SVGs to canvas first) or serialize SVG DOM for SVG export.

**Scope.** `web/compare.html` + new export helper module.

---

### F14. Keyboard navigation for lap pickers

**What.** Allow users to step through laps with arrow keys (↑/↓) while a picker is focused, auto-triggering re-render on each step.

**Scope.** `web/js/ui.js` picker event handlers.

---

### F15. Session file metadata panel

**What.** Add a collapsible panel showing session metadata from the sidecar JSON (sim, track, vehicle, setup, started/ended timestamps, row count, lap count).

**Scope.** `web/compare.html` + `web/js/ui.js` sidecar display logic.

---

## References

- [DESIGN.md](DESIGN.md) — Architecture, file format, milestone plan
- [RENDER_DESIGN.md](RENDER_DESIGN.md) — Rendering architecture, module structure, panel pipeline
- [m2-plan.md](m2-plan.md) — M2 implementation (write loop, Parquet shards, sidecar)
- [m3-plan.md](m3-plan.md) — M3 implementation (sectors in summary, recoverable metadata)
- [m4-plan.md](m4-plan.md), [m5-plan.md](m5-plan.md), [F1F2-plan.md](F1F2-plan.md) — Comparison app milestones
- [web-refactor-step10-handoff.md](web-refactor-step10-handoff.md) — Step 10 handoff (pickers.js extraction)

---

## Summary

**Refactoring complete.** `main.js` reduced from 1869 → 437 lines (-77%), all 81 tests passing, clear module boundaries established.

**Next priorities:**
1. **U3** — Fix Throttle/Brake panel colours (visual regression)
2. **U5** — Audit all panels for consistent colour/line-style
3. **U4** — Colour tooltip speed values by lap identity
4. **U2** — Enlarge circuit map for overlay readability

**Optional further refactoring:**
- Extract `PANEL_DEFS` to `panelConfig.js` (~50 lines → `main.js` ~390)
- Extract debug hooks to `debug.js` (~100 lines → `main.js` ~340)
