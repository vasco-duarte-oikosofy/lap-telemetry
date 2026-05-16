# F1 + F2 handoff — Circuit map + distance-range zoom + two bug fixes

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

---

## Fix 3 — Tooltip follows the cursor, not the top of the plot

**Symptom.** The info callout (distance / speed / Δt values) is rendered at a
fixed `top: 20px` inside `#plot-area`, so it always appears near the top of the
speed panel regardless of which panel the mouse is over. When hovering over the
Brake or Δt panel the tooltip is far from the cursor.

**What the user wants.** The tooltip should appear offset from the actual cursor
position so it reads like a floating label attached to the crosshair, visible
whichever panel the mouse is in.

**Fix.** In the `mousemove` handler, replace the hardcoded `const ty = 20;`
with a value derived from the mouse Y offset inside `#plot-area`, clamped so
the tooltip never overflows the container:

```javascript
// follow cursor vertically, offset up by ~30 px, clamped inside plot-area
const ty = Math.max(8, Math.min(e.clientY - rect.top - 30, rect.height - 130));
```

Adjust the offset and clamp margin to taste; the exact numbers are not
critical. Also offset it a bit to the right of the cursor line (the `tx`
calculation already does this; just ensure `ty` is no longer hardcoded).

---

## Fix 4 — Δt calculation is wrong for pre-F4 recordings

**Symptom.** When comparing two laps that the sector display confirms are
~0.1 s apart, the Δt trace shows swings of ±500 ms or more and oscillates
wildly rather than growing smoothly. See `screenshots/DeltaT bug.png` — the
bottom panel shows the oscillating Δt for a Barcelona LMP3 comparison.

**Root cause.** The `lap_distance_m` column in recordings made before F4 was
implemented updates at ~4 Hz (one new value every ~11 m at 130 km/h). When the
resampler sorts frames by distance, up to ~50 consecutive frames cluster at the
same distance value (they were all recorded during the 0.25 s between SHM
ticks). The JavaScript `Array.sort` order among equal-distance frames is
unspecified — different laps end up picking different frames from the cluster.
In a braking zone, one lap might get speed 240 km/h from the entry frame and
the other lap speed 80 km/h from the exit frame, both attributed to the same
1 m bin. The Δt integration treats this as a real speed difference (3× actual)
and the error accumulates and oscillates at every braking zone.

**Diagnosis first.** Before patching anything, the agent should verify:

1. Load a **post-F4 recording** (any session file recorded after the
   `_estimate_dist` commit). Run the same comparison. If the Δt trace is smooth
   and correct for the new file, the bug is purely in old data and the fix
   should be a UI-side warning rather than a formula change. If the Δt is
   still wrong on the new file, the formula itself is broken.

2. Check the resampler output for a pre-F4 lap: call
   `window.__resamplerDebug(key, segIdx)` on both the session and reference
   laps and print the speed at every 10th bin for 100 bins around a known
   braking zone (e.g. bins 900–1100). If the two speed arrays look erratic
   (not matching the smooth speed graph), the cluster-aliasing is confirmed.

**Fix for old recordings (primary path).** Add a stability pass to the
resampler: when sorting frames by distance, break ties by original frame index
(time order). This ensures all frames in a cluster are taken in the order they
were driven, so the interpolation at each 1 m bin picks a speed that is
monotonically related to the car's actual path through that braking zone.

Implementation: in `resample()`, change:
```javascript
idx.sort((a, b) => distances[a] - distances[b]);
```
to:
```javascript
// stable tie-break by frame index preserves time order within equal-distance clusters
idx.sort((a, b) => (distances[a] - distances[b]) || (a - b));
```
`Array.sort` in V8 is stable, so equal comparisons preserve the original order;
the explicit `|| (a - b)` makes it explicit regardless of engine.

After this fix, the two laps will still pick frames from different positions
within each cluster (they can't avoid it — the clusters are at different
positions per lap), but each lap will be internally consistent (time order),
which significantly reduces the oscillation amplitude. The fundamental limit
is the 11 m anchor spacing; the fix makes the best of bad data.

**Fix for new (F4) recordings.** F4 recordings have sub-meter spacing so there
are no clusters. No fix needed beyond verifying the Δt is correct.

**UI warning.** After the speed-stability fix, add a banner or badge when
the loaded session has coarse distance data. Detection heuristic: compute the
median frame-to-frame distance change for the chosen segment; if median > 2 m,
flag it as "legacy distance resolution — Δt accuracy limited". Show the warning
near the Δt panel label, not as a blocking error.

---

## What not to touch

- `lap_telemetry/` Python recorder — no changes needed for F1/F2.
- `scripts/test_m5.js` — do not edit; just ensure it still passes.
- `DESIGN.md` — update §11 to mark F1 and F2 as done once they ship.
- `CLAUDE.md` — update "Current state" to reflect M5 done + F1/F2 in progress.
