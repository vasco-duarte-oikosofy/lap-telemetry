# M6 handoff — lap colour customisation + ABS/TC capture + TinyPedal deltabest ingest

Three independent additions, grouped because they share the same plumbing
(file picker, store entries, sidecar pattern, regression suites). Read in
this order before writing any code:

1. `DESIGN.md` — §5.1 (schema), §7 (M6 line), §10 (O3 perf, accepted as-is),
   §11 (F1–F4 history; use it as the model for "what shipped, what didn't")
2. `CLAUDE.md` — current state, app surface, recorder layout
3. `web/compare.html` — the entire app. Pay attention to:
   - `:root` CSS variables (`--session`, `--ref`, `--throttle`, `--brake`, etc.)
   - `loadFile` + `loadSidecar` + `pendingSidecars` (the parquet/JSON pairing pattern)
   - `formatPickLabel` and `rebuildPickers` (where lap labels are built)
   - `ZOOM_LS_KEY` + `persistZoom` / `loadPersistedZoom` (the localStorage pattern)
4. `lap_telemetry/recorder/connect.py` — `Frame` dataclass, LMU/rF2 read_frame
5. `lap_telemetry/recorder/writer.py` — `_SCHEMA`, `append`, sidecar JSON
6. `scripts/test_m5.js`, `scripts/test_f1f2.js`, `scripts/test_m6_extras.js` —
   test pattern to extend, not replace
7. `F1F2-handoff-prompt.md` — handoff format for reference (not the content)

---

## What to produce

**First job: write `m6-plan.md`** in the same shape as `m5-plan.md` /
`F1F2-plan.md`: scope pieces (one section per feature), steps,
acceptance tests. Do not write any app or recorder code until the plan
is on disk and you've confirmed it back in 3–4 bullets.

After the plan is written, **proceed straight to implementation and
self-test** without waiting for review (user will be AFK). If you hit a
genuine architectural decision that needs user input, leave
`m6-test-report/BLOCKED.md` with the question and what you tried.

Test report: `m6-test-report/REPORT.md` summarising what ran, what passed,
screenshots. Add `m6-test-report/` to `.gitignore` if not already covered
by the `m*-test-report/` pattern.

---

## Feature 1 — Lap colour customisation

**What.** Currently `--session` (`#4fc3f7` cyan-blue) and `--ref` (`#ff9800`
orange) are hard-coded in the `:root` CSS block of `compare.html`. Let the
user change those two colours from the UI; persist the choice; reset to
defaults on demand.

**Why.** Personal preference, colour-blindness accessibility, future
multi-lap overlay (3+ traces will need a colour palette).

**Implementation sketch.**
- A small "Colours" control group (next to or under the loader panel —
  pick whichever crowds the layout least). Two `<input type="color">`
  pickers + a "reset" button.
- On change: write the new colour to `document.documentElement.style.setProperty('--session', value)` (and `--ref`).
  Every existing line, swatch, sector-marker uses these vars, so the change
  is global and free.
- Persist to `localStorage` under a new key (`lap-telemetry.colours.v1`).
  Restore on page load before any render.
- Reset button clears the storage and re-applies the original defaults
  from a constants block at the top of the script.

**Scope boundary.** Only `--session` and `--ref` for now. Other CSS vars
(`--throttle`, `--brake`, `--slip-fl`, `--dt-pos`, `--dt-neg`, `--sector-clr`)
stay defaults — they're channel/state colours, not lap identity. If
this turns out to need extending (e.g., for multi-lap overlay), do it
in a separate change.

**Acceptance tests.**
- T1: Picker change updates session line stroke + legend swatch immediately.
- T2: Reload page → colour persists.
- T3: "Reset" → both pickers revert to default values and `localStorage` key is cleared.
- T4: M5 + F1F2 + M6-extras suites still pass (the existing tests assume
  default colours; either the new control doesn't affect them, or update
  the tests in lock-step).

---

## Feature 2 — ABS / TC active flags (LMU-only)

**What.** Capture `abs_active` and `tc_active` boolean columns in new
recordings; show "the car helped you here" markers on the throttle and
brake panels in the app.

**Why.** Race-analysis value: knowing where ABS triggered tells you if
the brake pressure was on the limit, knowing where TC triggered tells
you if you tried to apply throttle too early on corner exit. DESIGN §5.1
already lists these as planned columns ("LMU-only; null on rF2").

**Investigation first.** The exact LMU SHM field name is not in any file
in this repo — read the vendored submodule:
- `pyLMUSharedMemory/` — find the telemetry struct definition. Look for
  fields named like `mABS`, `mTC`, `mElectronics`, or similar. LMU exposes
  driver-aid state somewhere on the per-vehicle telemetry struct; rF2's
  equivalent is likely absent or differently named.
- If the field is a *level* (0=off, 1+=active), normalise to a bool:
  `bool(level > 0)`.
- If you can't find it after 15 min, leave a BLOCKED.md with what you
  searched and what was in the relevant headers.

**Recorder change.**
- Add `abs_active: bool | None` and `tc_active: bool | None` to `Frame`
  in `connect.py`. Use `Optional[bool]` (i.e., the type is nullable) so
  rF2 can leave them as `None`.
- LMU `read_frame` populates from the SHM field you found.
- rF2 `read_frame` sets both to `None`.
- Append both fields in `writer.py`'s `_SCHEMA` and `append()`. Use
  `pa.field("abs_active", pa.bool_())` with `nullable=True`.
- Smoke-test with `lap-telemetry record --once` (need a live sim — if not
  available, do a synthetic test with `_BaseConnection` subclass mocking).

**App change.**
- Add `abs_active`, `tc_active` to the `COLUMNS` list. Existing parquets
  will be missing them — `readColumns` already handles missing columns
  via `missingCols`; leave the bins empty for those.
- Resample `abs_active` and `tc_active` along the same 1 m grid as
  everything else. Bool channels: nearest-neighbour interpolation
  (cluster averaging would give weird 0.5 values; round to 0/1).
- Render: small bottom-bar strip on the **brake** panel for `abs_active`
  (red bars) and on the **throttle** panel for `tc_active` (green bars).
  About 4 px tall, only shown when value > 0.5. Keep them inside the panel
  clip-path so zoom works.
- Tooltip: include `ABS:on` / `TC:on` lines when active at the cursor.

**Backward compat.** Existing recordings (no abs/tc columns) must still
load and render — the new strip simply doesn't appear when the columns
are missing. Verify this with one of the older sessions in `sessions/`.

**Acceptance tests.**
- T5: Fresh recording → `abs_active`, `tc_active` columns present.
- T6: Compare two laps from a fresh recording → ABS strip on brake
  panel, TC strip on throttle panel, both clip-pathed inside the panel
  bounds.
- T7: Compare two laps from a pre-feature recording → no strips, no
  console errors, all other panels render normally.
- T8: M5 + F1F2 + M6-extras suites still pass.

---

## Feature 3 — TinyPedal deltabest CSV ingest

**What.** Accept TinyPedal's deltabest CSV file as a "reference lap"
input. The user already has these files in their TinyPedal install
(typically `<TinyPedal>/deltabest/*.csv`). They want to compare a fresh
session lap against the saved best without having to record the best
again as a parquet.

**Why.** Closes the workflow loop for the most common day-to-day question
("did I beat my best?") without any extra recording step.

**Investigation first.** The TinyPedal deltabest CSV format isn't
documented in this repo — figure it out by:
1. Asking the user for a sample file path (or grab one from their
   TinyPedal install if accessible).
2. Reading TinyPedal's source if the user can't find one. The format is
   typically distance-vs-time pairs (`lap_distance_m, lap_time_s`) or
   distance-vs-speed; commonly with one row per metre.
3. Confirm: header row? Units? Newline convention? Delimiter? Float
   precision? Number of rows?

If you can't get a real file or can't read TinyPedal's source within
20 min, write a `BLOCKED.md` with what you tried and what you'd need.

**Implementation.**
- Extend the file-input `accept` attribute to include `.csv`.
- In `loadFile`, branch on extension: `.parquet` → existing path,
  `.json` → existing sidecar path, `.csv` → new TinyPedal path.
- New `loadDeltabestCsv(file)`:
  - Parse the CSV in-browser (`file.text()` then split lines).
  - Build a synthetic `entry` for the store with shape compatible with
    the existing path: `{ fileName, data, segments, hasSlip, hasSectors, sidecar, isDeltabest }`.
  - `data.lap_distance_m` and `data.lap_time_s` from the CSV; derive
    `data.speed_kph` if not present (`speed = ds/dt`).
  - Other channels (`throttle_norm`, `brake_norm`, etc.): empty arrays
    or absent — the app already handles missing channels.
  - One synthetic segment covering the whole file. `segments.length === 1`.
  - Synthetic sidecar with `vehicle_name = "TinyPedal deltabest"`,
    `setup_file_guess = null`.
- `formatPickLabel` and `rebuildPickers` already handle entries with
  custom sidecar values; verify their output makes sense for the
  deltabest entry (one option: "deltabest.csv / Lap 1 (—) · TinyPedal deltabest").
- The app's existing missing-column handling means panels without data
  for the reference simply show only the session trace. Δt still works
  if speed is present (which it is — derived if not).

**Scope boundary.** Read-only ingest. We don't write deltabest CSVs back,
don't try to keep them in sync with TinyPedal, don't auto-discover them
from the install path.

**Acceptance tests.**
- T9: Load a TinyPedal deltabest CSV → appears in session list with
  "TinyPedal deltabest" tag; appears in picker as a single-lap option.
- T10: Compare a parquet session lap against the deltabest as reference
  → speed panel shows both traces, Δt panel shows the integration
  result, panels with no deltabest data show only the session trace
  (no errors).
- T11: Mixed file load — drop a parquet, a sidecar, and a deltabest CSV
  in one multi-select → all three end up in the right places.
- T12: Existing M5 + F1F2 + M6-extras suites still pass.

---

## Context the files won't tell you

- The app is a single `web/compare.html` with all JS/CSS inline, ESM CDN
  imports, no build step. Do not introduce a bundler.
- The store entries have a defined shape (see `loadFile`); adding fields
  is fine, removing or renaming requires updating every consumer.
- Bool columns in parquet via pyarrow: `pa.field("abs_active", pa.bool_())`.
  Don't use int8 or uint8 — keeps types tidy.
- `readColumns` calls `parquetRead` with the requested column list and
  silently skips missing ones (logged once). New columns "just work" for
  existing files — they show as empty arrays.
- Sidecars without all the F1F2 fields (older recordings) are tolerated
  — `entry.sidecar?.vehicle_name ?? 'unknown'` patterns are everywhere.
- The persistent-zoom code (`ZOOM_LS_KEY`) is the model for any
  `localStorage` work in this codebase: try/catch wrappers, version
  suffix in the key, validate-on-read.
- `scripts/test_m6_extras.js` is the model for new tests. Use the same
  file-injection pattern (DataTransfer + base64).
- For the TinyPedal CSV test, fabricate a synthetic CSV in-line in the
  test (~50 rows of `distance,time`) — no need to ship a real sample.
- For the LMU ABS/TC test, you need a fresh recording to verify the
  columns are populated. The two latest `sessions/session_20260510T142624Z*`
  files were recorded after F4 was fixed but before this work, so they
  won't have the new columns — that's the "old format" baseline.
- Don't use `AttachConsole + GenerateConsoleCtrlEvent` to send Ctrl+C to
  background processes — it kills the Claude Code session. Use TaskStop
  or ask the user to Ctrl+C.

---

## Environment

- Windows 10, PowerShell. Bash also available.
- Node v20, Playwright + Chromium pre-installed.
- Python: system interpreter has pyarrow but not numpy. `lap-telemetry`
  CLI resolves to the same interpreter.
- Run after recorder changes:
  - `lap-telemetry record --once` (smoke; needs live sim)
  - `lap-telemetry summary sessions/<latest>.parquet`
- Run after app changes:
  - `node scripts/test_m5.js` — must stay 25/25
  - `node scripts/test_f1f2.js` — must stay 13/13
  - `node scripts/test_m6_extras.js` — must stay 17/17
  - new `node scripts/test_m6.js` — your new assertions

---

## What not to touch

- `lap_telemetry/recorder/connect.py` `_estimate_dist` — F4 fix is correct.
- `lap_telemetry/recorder/writer.py` shard merge / orphan recovery logic.
- `web/compare.html` Δt formula, resampler stable sort, persistent zoom.
- `scripts/test_m5.js`, `test_f1f2.js`, `test_m6_extras.js` — extend
  with new files, don't edit these.
- DESIGN.md §10 O3 — that's a recorded decision, not a TODO.

After shipping: update `DESIGN.md` §11 to add a "F5/F6/F7 — shipped"
block (or rename the section as the list grows), and update `CLAUDE.md`
"Current state" to mention abs/tc columns and TinyPedal CSV ingest.
