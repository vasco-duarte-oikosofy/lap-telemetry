# F1 + F2 handoff — Circuit map + distance-range zoom

Read these before writing any code, in this order:

1. `DESIGN.md` §11 — F1 and F2 spec (what, why, implementation sketch)
2. `m5-plan.md` — shape of a plan file; F1/F2 notes at the bottom
3. `web/compare.html` — the entire current app (M5, 8 panels, unified loader)
4. `scripts/test_m5.js` — existing Playwright test to extend, not replace

---

## What F1 and F2 are

**F1 — Circuit map.**  
A full SVG rendering of the circuit outline drawn from `pos_x_m` / `pos_z_m`
world coordinates already stored in every parquet. Shown alongside the
telemetry panels — not a thumbnail, a readable map that fills the space
available. As the user moves the mouse across any telemetry panel, a dot
moves on the circuit map to show where on track that distance corresponds to.

**F2 — Distance-range zoom.**  
Click and drag horizontally across any panel to select a distance window. All
panels (including the circuit map) update immediately to show only that range.
The selected range is highlighted on the circuit map as a coloured arc. A
reset gesture (double-click or Escape) restores the full-lap view.

F1 and F2 are tightly coupled: the zoom arc on the map is part of F2's output,
and the cursor dot on the map is part of F1's cursor handling. Plan and
implement them together.

---

## What to produce

**Your first job is to write `F1F2-plan.md`** — same structure as `m5-plan.md`:
scope pieces (e.g. A. map data + render, B. cursor dot, C. zoom interaction,
D. map arc, E. tests), steps, acceptance tests. Do not write any app code until
the plan is on disk.

After the plan is written, confirm it back in 3–4 bullets, then **proceed
straight to implementation and self-test** without waiting for review (the user
will be AFK).

---

## Context the files won't tell you

- The app is a single `web/compare.html` with all JS/CSS inline. No build step.
  Dependencies are loaded from CDN via `<script type="module">`.
- Parquet files are in `sessions/`. The two main fixtures for testing:
  - `session_20260510T093245Z_circuit-de-barcelona_lmu.parquet` — 6-lap clean
  - `session_20260510T091432Z_circuit-de-barcelona_lmu.parquet` — restart session
  - `sessions/reference_lap_circuit-de-barcelona_lap5.parquet` — single lap
- `pos_x_m` and `pos_z_m` are already read by `readColumns` (they are in
  `COLUMNS` — verify before assuming). If they are not, add them.
- The circuit coordinate system: `pos_x_m` is the world X, `pos_z_m` is world
  Z. In LMU, the horizontal plane is X/Z (Y is up). A top-down map is
  `(pos_x_m, pos_z_m)` projected and normalised to the SVG viewport. Verify
  the axis orientation looks right once rendered (may need to flip Z).
- The user called this a "circuit map", not a minimap — it should be large
  enough to read clearly. The DESIGN sketch says ~28% of page width; treat that
  as a lower bound, not an upper bound. If a side-by-side layout crowds the
  panels, a layout with the map above or below the panels is acceptable —
  document the tradeoff in the plan.
- The `resample()` function already produces 1 m-bin arrays for every channel.
  `pos_x_m` and `pos_z_m` need the same treatment so the cursor can index them
  by `binIdx`. Add them to `currentSessionBins` in `renderAll`.
- For the zoom, the constraint is: **re-render all panels** when the zoom
  changes. Panels are already pure functions of bin data + maxDist; add a
  `zoomRange = {start, end}` to app state, pass it into `toX()`, and call
  `renderAll` again on zoom commit. Do not try to animate or incrementally
  update — full re-render is fast enough.
- The existing cursor hairline (`#cursor-line`) is a `position: absolute` div.
  With zoom, the cursor mapping changes: `fracX` now maps to
  `[zoomRange.start, zoomRange.end]` instead of `[0, maxDist]`. Update the
  cursor handler.

---

## Environment

- Windows 10, PowerShell. Bash also available.
- `node --version` → v20. `npm` available. Playwright + Chromium already
  installed (`node_modules/` exists; `npx playwright install chromium` was
  already run).
- The system Python on PATH (`python`) has pyarrow but not numpy.
  `lap-telemetry` CLI resolves to the same interpreter.
- Do **not** use `AttachConsole` + `GenerateConsoleCtrlEvent` to send Ctrl+C
  to background processes — it kills the Claude Code session. Use `TaskStop`
  or ask the user to Ctrl+C.
- Run `lap-telemetry summary sessions/<latest>.parquet` as a smoke test after
  any Python changes. Run `node scripts/test_m5.js` (the existing M5 suite)
  after any `compare.html` changes to confirm nothing regressed. Both must pass
  before you write the F1F2 tests.

---

## AFK testing

Write `scripts/test_f1f2.js` — a Playwright test that:

1. Loads both the clean 6-lap session and the reference lap, compares lap 4 vs
   lap 5 (the baseline scenario from M5 tests).
2. **Circuit map assertions:**
   - A map SVG element exists and contains a `<polyline>` for the track
     outline.
   - The track outline has enough points to be a recognisable circuit shape
     (assert `points` attribute split count > 200).
   - On `mousemove` to the centre of a telemetry panel, a `<circle>` or
     equivalent cursor element is visible in the map SVG and has moved from its
     initial position.
3. **Zoom assertions:**
   - Simulate a drag from 20% to 60% of the plot width.
   - After drag, the x-axis labels on the first panel show a sub-range of the
     total distance (not 0 to max).
   - A zoom-arc element is present in the map SVG.
   - After double-click (or Escape), the x-axis labels return to full range.
4. Screenshots at: initial load, after compare, after hover (cursor on map),
   after zoom drag, after zoom reset.
5. Console log captured; any error fails the test.
6. Resampler and Δt assertions from `test_m5.js` do **not** need to be
   repeated — reference them by name in `REPORT.md` as "inherited from M5,
   still passing".

Drop all output into `f1f2-test-report/` (already gitignored via the
`m*-test-report/` pattern — add `f1f2-test-report/` explicitly if needed).
Write `f1f2-test-report/REPORT.md` summarising what ran.

If a test fails, diagnose and fix, then re-run. Only stop if you hit a genuine
architectural decision that requires user input — in that case leave
`f1f2-test-report/BLOCKED.md` with the question and what you tried.

---

## What not to touch

- `lap_telemetry/` Python recorder — no changes needed for F1/F2.
- `scripts/test_m5.js` — do not edit; just ensure it still passes.
- `DESIGN.md` — update §11 to mark F1 and F2 as done once they ship.
- `CLAUDE.md` — update "Current state" to reflect M5 done + F1/F2 in progress.
