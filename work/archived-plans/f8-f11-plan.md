# F8–F11 implementation plan

## F8. ABS / TC full panels

### Context
- `abs_active` / `tc_active` bins already land in `currentSessionBins` via the
  general channel-resampling loop (once panels with those channels exist) or via
  the activity-strip resampling code. The two paths share the same
  `currentSessionBins[col]` key; whichever runs first wins.
- Pre-M6 parquets and rF2 sessions produce zero-filled `Float64Array` via the
  existing fallback in the channel loop — no `undefined`, just all-zero bins.
- Hidden condition: `!currentSessionBins['abs_active'].some(v => v >= 0.5)`.

### Steps
1. Add two entries to `PANEL_DEFS` (after `brake` and `throttle` respectively):
   ```js
   { id: 'abs', label: 'ABS active',
     channels: [{ col: 'abs_active', trace: 'session', color: 'var(--brake)', dash: false, step: true }],
     yFixed: [0, 1], height: 50, midline: 0.5, zeroline: false },

   { id: 'tc', label: 'TC active',
     channels: [{ col: 'tc_active', trace: 'session', color: 'var(--throttle)', dash: false, step: true }],
     yFixed: [0, 1], height: 50, midline: 0.5, zeroline: false },
   ```
   Default order: Speed → Throttle → TC → Brake → ABS → RPM → Gear → Steering → Slip → Δt.

2. In `renderPanel`, add midline support: when `def.midline != null`, render a
   dashed horizontal rule at that y value (same style as `zeroline` but at the
   specified y, not zero).

3. In `renderAll`'s render loop, detect hidden state per panel:
   ```js
   if ((def.id === 'abs' || def.id === 'tc') && !hasAbsTc) { /* render placeholder */ }
   ```
   where `hasAbsTc` = `currentSessionBins['abs_active'].some(v => v >= 0.5) || currentSessionBins['tc_active'].some(v => v >= 0.5)`.
   Render a one-line placeholder div (same style as the existing slip-absent
   placeholder) so the panel-wrap still exists and can be reordered (F9).

4. Update `DEFAULT_PANEL_ORDER` (F9 companion) to include `abs` and `tc`.

### Acceptance tests
- T1: Post-M6 LMU parquet → ABS and TC panel-wraps visible; each has a polyline
  with at least one segment above y=0.5; midline at y=0.5 rendered.
- T2: Pre-M6 parquet or rF2 session → ABS/TC panel-wraps show placeholder text
  `no ABS/TC data`; all other panels render normally; no console errors.
- T3: Zoom into a distance range containing an ABS event → ABS panel zooms with
  the rest; trace clips at the clip-path boundary.

---

## F9. Draggable panel reorder

### Steps
1. Declare constants and state near the top of the `<script>`:
   ```js
   const PANEL_ORDER_LS_KEY = 'lap-telemetry.panel-order.v1';
   const DEFAULT_PANEL_ORDER = PANEL_DEFS.map(d => d.id);
   let panelOrder = loadPersistedPanelOrder() || [...DEFAULT_PANEL_ORDER];
   ```

2. `loadPersistedPanelOrder()` — same pattern as `loadPersistedZoom`:
   - Read key → JSON.parse → validate it's an array of exactly the known IDs
     (all present, no duplicates, no unknown strings) → return null on any
     failure so the default silently wins.

3. `persistPanelOrder(order)` — remove key if order matches default; set otherwise.

4. In `renderAll`, replace the `PANEL_DEFS`-ordered loop with:
   ```js
   for (const panelId of panelOrder) {
     const def = PANEL_DEFS.find(d => d.id === panelId);
     if (!def) continue;
     ...
   }
   ```
   `showXLabels` assignment: mark the last non-hidden panel in the rendered list.
   The dt panel always shows x-labels regardless of position.

5. Add `draggable="true"` to each `panel-wrap` div. Add a grip handle element
   inside the panel-label div: `<span class="drag-handle">⠿</span>`.

6. After `panelsDiv.innerHTML = ''` and panels are appended, attach drag handlers
   via event delegation on `panelsDiv`:
   - `dragstart`: store `e.currentTarget.dataset.panelId` in `state.dragId`.
   - `dragover`: `e.preventDefault()`, add CSS class `drag-over` to target wrap.
   - `dragleave`/`dragend`: remove `drag-over`.
   - `drop`: compute target panel index, splice `panelOrder`, persist, call
     `renderAll(...state.currentRenderParams)`.

   Each `panel-wrap` gets `data-panel-id="${def.id}"`.

7. CSS additions:
   ```css
   .drag-handle { cursor: grab; opacity: 0.4; margin-right: 6px; user-select: none; }
   .panel-wrap.drag-over { border-top: 2px solid var(--accent); }
   ```

8. "Reset order" button: add to the pickers row area (right side, next to the
   Compare button or below it). On click: clear localStorage key, restore
   `panelOrder = [...DEFAULT_PANEL_ORDER]`, call
   `renderAll(...state.currentRenderParams)` if data is loaded.

### Acceptance tests
- T4: Drag Δt panel to the top → it renders above Speed; cursor updates all
  panels; zoom syncs all panels.
- T5: Reload the page → custom order is restored; rendered order matches saved.
- T6: Click reset → default order restored; localStorage key cleared.
- T7: Load a new lap after reordering → new render respects the persisted order.

---

## F10. Y-axis legibility — Δt and slip angle

### Steps
1. Add a `computeNiceYTicks(yMin, yMax, plotH, niceSteps)` helper function:
   ```
   For each step in niceSteps (ascending):
     startTick = ceil(yMin / step) * step
     ticks = [startTick, startTick + step, ...]  while <= yMax
     count = ticks.length
     pixGap = plotH / max(count - 1, 1)
     if count >= 3 && count <= 5 && pixGap >= 30: return ticks
   Fallback: use the last step that gives count >= 3 (even if pixGap < 30).
   ```

2. Add `niceSteps` field to the `dt` and `slip` panel defs:
   - `dt`:   `niceSteps: [1, 2, 5, 10, 25, 50, 100, 250, 500, 1000]`
   - `slip`:  `niceSteps: [0.5, 1, 2, 5]`

3. In `renderPanel` y-tick generation (`if (ch === def.channels[0]) { ... }`):
   replace the current `const start = Math.ceil(yMin/step)*step; for...` with:
   ```js
   const yTicks = def.niceSteps
     ? computeNiceYTicks(yMin, yMax, plotH, def.niceSteps)
     : (() => { const t=[]; const s=def.yStep; ... return t; })();
   ```

4. In `renderDtPanel` y-tick generation: same substitution using `def.niceSteps`.

5. The helper must be defined before both render functions; no data or resampling
   changes.

### Acceptance tests
- T8: Any parquet with non-trivial Δt range → Δt panel shows 3–5 Y-axis labels;
  labels are round numbers; no overlapping text.
- T9: Any parquet → slip panel shows 3–5 Y-axis labels with 0.5° or 1° steps; no
  overlapping text.
- T10: Zoom into a small distance range → Y tick count stays in the 3–5 range;
  labels remain readable.

---

## F11. Gear panel height ×1.3

### Steps
1. Add `heightMultiplier: 1.3` to the gear panel def. All other defs omit it
   (implicitly 1.0).

2. In `renderPanel`, compute effective height:
   ```js
   const H = Math.round(def.height * (def.heightMultiplier ?? 1.0));
   ```
   This drives `plotH`, `viewBox`, and the `<clipPath>` rect height.

3. No other panels are affected; the plot container grows by the delta naturally.

### Acceptance tests
- T11: Any parquet → gear panel computed height ≈ `PANEL_H * 1.3`
  (i.e., `Math.round(60 * 1.3) = 78 px` in viewBox units).
- T12: Y-axis of gear panel spans R → 6 with visible gaps between adjacent gears.
- T13: Zoom into a braking zone → gear trace clips correctly; cursor tooltip shows
  gear value.

---

## Test file

New file: `scripts/test_f8f9f10f11.js` (Playwright + Chromium).
Uses the existing post-M6 session `session_20260511T143916Z*.parquet` for T1/T3/T8/T9 and
a pre-M6 session for T2. Extends the existing session-loading helpers.

Must-stay-green: `test_m5.js` 25/25, `test_f1f2.js` 13/13,
`test_m6_extras.js` 17/17, `test_m6.js` 26/26.

---

## Regression guard

After every batch of changes:
```
node scripts/test_m5.js && node scripts/test_f1f2.js && node scripts/test_m6_extras.js && node scripts/test_m6.js
```

Then run the new `node scripts/test_f8f9f10f11.js` once all four features are in.
