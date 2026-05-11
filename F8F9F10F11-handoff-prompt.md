# F8–F11 handoff — ABS/TC panels + draggable reorder + Y-axis legibility + gear height

Four independent UI improvements to `web/compare.html`. Read in this order
before writing any code:

1. `CLAUDE.md` — current state, app surface, key facts
2. `DESIGN.md` §11 (F6 for ABS/TC context) and §12 (F8–F11 specs — your
   source of truth for scope and acceptance criteria)
3. `web/compare.html` — the entire app. Pay attention to:
   - Panel definitions array (id, label, channels, yDomain, etc.)
   - `renderPanel` — how a single panel SVG is built
   - `PANEL_H`, `PAD`, clip-path setup
   - `yTicks` or equivalent tick-generation helper
   - `renderActivityStrip` — the existing ABS/TC strip renderer (F8 extends this)
   - `ZOOM_LS_KEY` / `persistZoom` / `loadPersistedZoom` — localStorage pattern
   - `dragstart`/`dragover`/`drop` if any drag handlers already exist
4. `scripts/test_m6.js` and `scripts/test_m6_extras.js` — test patterns to
   extend, not replace

---

## What to produce

**First job: write `f8-f11-plan.md`** in the same shape as `m6-plan.md`:
one section per feature, implementation steps, acceptance tests. Confirm it
back in 3–4 bullets before writing any app code.

After the plan is written, **proceed straight to implementation and
self-test** without waiting for review. If you hit a genuine architectural
decision that needs user input, leave `f8f9f10f11-test-report/BLOCKED.md`
with the question and what you tried.

Test report: `f8f9f10f11-test-report/REPORT.md` summarising what ran, what
passed, screenshots. Add `f8f9f10f11-test-report/` to `.gitignore`.

---

## F8. ABS / TC full panels

**What.** Promote ABS and TC from 4 px activity strips on the brake/throttle
panels into first-class binary panels rendered at full panel height, placed in
the default panel order after the Brake and Throttle panels respectively (or
grouped together at the bottom — pick whichever reads more cleanly). The
existing 4 px strips stay; the new panels give a zoomable, cursor-readable
trace of exactly when each aid intervened.

**Why.** The strips are a useful quick-glance overlay but are too thin to read
precisely at a corner level. A full panel lets the user zoom in and see exactly
which braking zone triggered ABS, or on which corner TC was cutting power.

**Implementation.**
- Two new entries in the panel definitions array: `abs` and `tc`.
- Y-axis fixed 0–1 with a single midline at 0.5; no need for the standard
  auto-range tick logic.
- Session trace only — reference lap ABS/TC is not shown (same rationale as the
  existing tooltip: the user is analysing their own aid intervention, not
  comparing to a reference).
- Hide the panel entirely when the loaded session has no ABS/TC data (pre-M6
  parquet or rF2 session) — `bins.abs_active` is empty or all-zero. A
  `data-hidden` attribute or CSS `display:none` on the panel `<div>` is fine.
- Reuse the resampled `abs_active` / `tc_active` bin arrays already computed
  for the strip renderer; no new resampling needed.

**Acceptance tests.**
- T1: Load a post-M6 LMU parquet → ABS and TC panels appear in the panel stack,
  each with at least one visible rect/polyline above the 0.5 midline.
- T2: Load a pre-M6 parquet or any rF2 session → ABS and TC panels are hidden;
  all other 8 panels render normally; no console errors.
- T3: Drag-zoom over a range containing an ABS event → the ABS panel zooms
  with the rest; the clip-path clips the trace correctly.

---

## F9. Draggable panel reorder

**What.** The user can drag any panel up or down to reorder them. The new order
persists in `localStorage` so it survives page reloads. A reset button in the
toolbar (or next to the existing "Reset zoom" button) restores the default order.

**Why.** The fixed order (Speed → Throttle → Brake → RPM → Gear → Steering →
Slip → Δt) puts the most-compared channels far apart. Pulling Δt next to Speed,
or Throttle next to Brake, removes the need to scroll between the panels the
user cares about most.

**Implementation.**
- Each panel `<div>` gets `draggable="true"` and a drag handle (a small grip
  icon or just the panel label area).
- `dragstart` records the dragged panel's id; `dragover` on a sibling prevents
  default and shows a visual insertion indicator; `drop` commits the reorder.
- Maintain a `panelOrder` array in app state (default: the current hard-coded
  order). On drop, splice the dragged id to the new position, re-render the
  panel container, persist.
- Persist as a JSON array of panel ids in `localStorage` under
  `lap-telemetry.panel-order.v1`.
- `loadPersistedPanelOrder()`: read + validate (array of known ids, length
  matches); return null on any validation error so the default silently wins.
- Reset button: clear the localStorage key, restore the default order, re-render.
- The existing zoom, cursor, and map interactions must work regardless of panel
  order — panels are re-rendered from state, not mutated in-place.

**Acceptance tests.**
- T4: Drag the Δt panel to the top → it renders above Speed; cursor still
  updates all panels; zoom still syncs all panels.
- T5: Reload the page → custom order is restored; rendered panel order matches
  what was saved.
- T6: Click reset → default order is restored; localStorage key is cleared.
- T7: Load a new lap after reordering → new render respects the persisted order.

---

## F10. Y-axis legibility — Δt and Slip Angle panels

**What.** Fix the Y-axis tick spacing on the Δt panel and the slip-angle panel
so the labels are readable. Currently both panels can produce 6–8 ticks crammed
into a short pixel range, causing overlapping or near-unreadable text.

**Fix.**
- In the tick-generation logic (wherever `yTicks` or equivalent is computed),
  enforce: minimum 30 px gap between adjacent tick labels; between 3 and 5
  labels visible at any zoom level.
- Round tick values to the nearest "nice" step: for Δt (milliseconds) use
  steps from `[1, 2, 5, 10, 25, 50, 100, 250, 500, 1000]`; for slip angle
  (degrees) use steps from `[0.5, 1, 2, 5]`. Pick the smallest step that
  keeps tick count ≤ 5.
- The same helper change will improve any other panel where the auto-range
  produces an awkward step — that's fine and expected.

**Scope.** Change is confined to the tick-generation helper and wherever it is
called for Y-axis rendering. No data, resampling, or panel layout changes.

**Acceptance tests.**
- T8: Load any parquet with a clearly non-trivial Δt range → Δt panel shows
  3–5 Y-axis labels with no overlapping text; labels are round numbers (not
  e.g. 37.3 ms, 74.6 ms).
- T9: Load any parquet → slip-angle panel shows 3–5 Y-axis labels with
  0.5° or 1° steps; no overlapping text.
- T10: Zoom into a small distance range → tick count stays in 3–5 range,
  labels stay readable.

---

## F11. Gear panel height ×1.3

**What.** Increase the gear panel's rendered height by 30% relative to all
other panels. The current height compresses the 8-step gear range (R, N, 1–6)
so adjacent gears are barely one pixel apart, making shift points hard to read.

**Implementation.**
- Add a `heightMultiplier` field to the panel definition objects (default 1.0;
  gear panel set to 1.3).
- In `renderPanel` (and wherever the panel container height is calculated),
  multiply `PANEL_H` by `def.heightMultiplier ?? 1.0` for that panel's SVG
  height, clip-path height, and y-axis scaling.
- The overall plot container grows by the delta; no other panels are affected.

**Acceptance tests.**
- T11: Load any parquet → gear panel is visibly taller than other panels
  (measure computed height: should be ≈ `PANEL_H * 1.3`).
- T12: Y-axis of gear panel spans R → 6 with visible gaps between gear steps.
- T13: Zoom into a braking zone → gear trace clips correctly inside the taller
  panel bounds; cursor tooltip still shows gear value.

---

## Context the files won't tell you

- The app is a single `web/compare.html` with all JS/CSS inline, no build step,
  ESM CDN imports. Do not introduce a bundler or split the file.
- ABS/TC bin arrays are already resampled as part of the standard `resample()`
  pass — check the column wiring in `readColumns`/`COLUMNS` and the
  `renderActivityStrip` call sites to see where they land.
- Bool columns resample to floats via linear interp; the strip renderer rounds
  at >= 0.5. The new F8 panels should use the same approach.
- For F9, browser native drag-and-drop (`draggable="true"`) works fine in the
  `file://` origin the app runs on. No library needed.
- The persistent-zoom code (`ZOOM_LS_KEY`) is the established pattern for any
  new localStorage work: try/catch wrappers, version suffix in the key,
  validate-on-read, clear + restore on reset.
- Don't use `AttachConsole + GenerateConsoleCtrlEvent` to send Ctrl+C to
  background processes — it kills the Claude Code session. Use TaskStop or ask
  the user to Ctrl+C.
- The session files in `sessions/` include both pre-M6 parquets (no abs/tc
  columns) and the post-M6 recording from 2026-05-11 (Circuit de Barcelona,
  `session_20260511T143916Z*`) which has real abs/tc data.

---

## Environment

- Windows 10, PowerShell. Bash also available.
- Node v20, Playwright + Chromium pre-installed.
- Python: system interpreter has pyarrow. `lap-telemetry` CLI available.
- Run after app changes:
  - `node scripts/test_m5.js` — must stay 25/25
  - `node scripts/test_f1f2.js` — must stay 13/13
  - `node scripts/test_m6_extras.js` — must stay 17/17
  - `node scripts/test_m6.js` — must stay 26/26
  - new `node scripts/test_f8f9f10f11.js` — your new assertions

---

## What not to touch

- `lap_telemetry/recorder/` — no recorder changes needed for any of these.
- `web/compare.html` Δt formula, resampler stable sort, loadDeltabestCsv.
- `scripts/test_m5.js`, `test_f1f2.js`, `test_m6.js`, `test_m6_extras.js` —
  extend with new test files, don't edit these.
- DESIGN.md §10 O3 — recorded decision, not a TODO.

After shipping: update `DESIGN.md` §12 to mark F8–F11 as shipped, and update
`CLAUDE.md` "Current state" to mention the new panels, draggable order, and
Y-axis fix.
