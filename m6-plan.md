# M6 — lap colour customisation + ABS/TC capture + TinyPedal deltabest CSV ingest

**Goal:** Three independent quality-of-life additions that share plumbing
(file picker, store entries, sidecar pattern, regression suites) but each
ship as its own slice. Implementation order is (1) → (2) → (3); tests
extend, not replace, the existing M5 / F1F2 / M6-extras suites.

Reference shape: `m5-plan.md`, `F1F2-plan.md`. Plan first, code after.

---

## Feature 1 — Lap colour customisation

### A. Defaults block + colour state

**What.** Today `--session` (`#4fc3f7`) and `--ref` (`#ff9800`) are hard-baked
in the `:root` CSS at the top of `web/compare.html`. Move the two literals
into a single `LAP_COLOUR_DEFAULTS` constant in the script block (mirrors
`ZOOM_LS_KEY` / `loadPersistedZoom`), so reset and persistence draw from
one source of truth.

```javascript
const LAP_COLOUR_DEFAULTS = { session: '#4fc3f7', ref: '#ff9800' };
const LAP_COLOUR_LS_KEY   = 'lap-telemetry.colours.v1';
```

The CSS `:root` keeps the same hex literals — that way an unsupported
`localStorage` (e.g. `file://` with strict settings) still renders correctly.

### B. Pickers UI

**Layout.** Add a small "Colours" row inside the existing loader panel, to
the right of the load button on the same line — keeps vertical real estate
unchanged. Two `<input type="color">` controls (label "Session" / "Ref")
plus a tiny "reset" `<button>`. Style: 22 × 22 px swatches, native
control, no extra CSS framework.

```html
<span class="colour-controls">
  <label>Session <input type="color" id="colour-session"></label>
  <label>Ref     <input type="color" id="colour-ref"></label>
  <button id="colour-reset" class="load-btn">reset</button>
</span>
```

### C. Apply / persist / restore

- `applyLapColour(slot, value)` — sets `document.documentElement.style
  .setProperty(--${slot}, value)`. Used by both the picker `change`
  handlers and the load-time restore.
- `persistLapColours()` — writes `{session, ref}` to localStorage (try/
  catch like `persistZoom`). If both values equal the defaults, remove
  the key (parallel to how persisted zoom clears at full range).
- `loadPersistedColours()` — read + validate `^#[0-9a-fA-F]{6}$`; return
  null on parse error.
- On page load (`DOMContentLoaded`-equivalent — script already runs at
  body end so just call inline once): apply persisted → fall back to
  defaults; sync the two `<input>` values to whatever was applied.
- Reset button: clear localStorage key, re-apply defaults to CSS vars
  *and* sync the two inputs back to default hex.

### D. Re-render on change

The existing SVGs use `stroke="var(--session)"` / `stroke="var(--ref)"`
inline strings (compiled per panel render), so changing the CSS var is
**not** enough — once the SVG is in the DOM, the inline `stroke` attribute
on each `<polyline>` is a fixed string referencing the var, but browsers
re-resolve it on the next paint. Verified by spot-check: `<polyline
stroke="var(--session)">` repaints when the var changes.

If empirical testing shows a panel doesn't repaint (e.g. some browsers
cache the resolved colour), call `renderAll(...state.currentRenderParams)`
on each picker change. Keep this as a fallback; the cheap path is just
the CSS var update.

The legend swatches use `style="background:var(--session)"` — same story.

### E. Acceptance tests (T1–T4)

- T1: change session picker to `#ff00ff` → first speed-panel polyline
  has computed stroke `rgb(255,0,255)` (or the CSS var resolves to it).
- T2: reload the page → both pickers report the persisted hex; first
  polyline still magenta.
- T3: click reset → pickers go back to defaults, `localStorage` key is
  gone, polyline stroke resolves to default `#4fc3f7`.
- T4: M5 + F1F2 + M6-extras suites still pass. (Existing tests assume
  default colours but never read swatch values, so this should hold —
  if a test relies on a hex literal, fix the test in lockstep.)

---

## Feature 2 — ABS / TC active flags (LMU-only)

### A. SHM investigation result (already done, locked here)

Confirmed in `pyLMUSharedMemory/lmu_data.py:159-160` on the `LMUTelemetry`
per-vehicle struct:

```c
mLapInvalidated  : c_bool
mABSActive       : c_bool        // true only while ABS is currently triggering
mTCActive        : c_bool        // true only while TC is currently triggering
mSpeedLimiterActive : c_bool
```

These are real booleans (not levels), so no `bool(level > 0)` mapping is
needed. They live next to `mLapInvalidated`, which we already read. rF2
side has neither (`grep` over `pyRfactor2SharedMemory` returns 0 hits) —
nullable `bool` in the schema is the right call.

### B. Recorder change

**`lap_telemetry/recorder/connect.py`:**
- Add to `Frame`:
  ```python
  abs_active: Optional[bool]
  tc_active: Optional[bool]
  ```
- In `LMUConnection.read_frame`, populate from `tele_v.mABSActive` /
  `tele_v.mTCActive` (cast to `bool(...)` for safety — ctypes `c_bool`
  values come back as Python bool already, but explicit is fine).
- In `RF2Connection.read_frame`, set both to `None`.

**`lap_telemetry/recorder/writer.py`:**
- Append two fields to `_SCHEMA`:
  ```python
  pa.field("abs_active", pa.bool_(), nullable=True),
  pa.field("tc_active", pa.bool_(), nullable=True),
  ```
- Append two lines to `SessionWriter.append`:
  ```python
  b["abs_active"].append(frame.abs_active)
  b["tc_active"].append(frame.tc_active)
  ```

**Backwards compat.** Pre-M6 parquets simply lack these columns. The
schema isn't versioned — readers (`summary.py`, the app) skip missing
columns silently.

### C. Recorder smoke test (synthetic)

A live LMU is not guaranteed to be running in CI. We get coverage two
ways:

1. **Synthetic Frame round-trip**: a tiny pytest-style script
   (`scripts/check_abs_tc_writer.py`) constructs two `Frame`s — one with
   `abs_active=True, tc_active=False`, one with both `None` — feeds them
   through a `SessionWriter`, then re-reads with pyarrow and asserts the
   two new columns exist with the right values. This proves schema +
   nullable handling. Run from the m6 test suite as a subprocess.

2. **Live recording (manual, only if LMU is up)**: `lap-telemetry record
   --once` → check the printed frame mentions `abs_active`/`tc_active`.
   Document this in REPORT.md as "manual smoke pending live LMU." Don't
   block the suite on it.

### D. App change — column wiring

In `web/compare.html`:

- Add `'abs_active'` and `'tc_active'` to the `COLUMNS` array.
- `loadFile` already discriminates missing columns via
  `readColumns({missingCols})` — the new columns will be reported absent
  on pre-M6 files, no error.
- `data.abs_active` / `data.tc_active` will be empty arrays for old
  files; the renderer treats that as "no strip."

### E. App change — resampling bool channels

`resample()` currently linearly interpolates via `interpAt`. For booleans
this gives 0.5 at transitions, which is wrong. Two clean options:

1. **Round after resample** — keep the existing pipeline, then map
   `>= 0.5 → true, else false` in the renderer. Easiest; no resampler
   change.
2. **Nearest-neighbour resample helper** — new `resampleNearest()` that
   picks the value of the closest sample. Cleaner but more code.

Pick (1) — it's a 4-line change in the strip renderer and keeps
`resample()` single-purpose. (Note: source data is `0|1` integers via
hyparquet's bool → uint8 path; the linear interp + `>=0.5` round
preserves transition timing within ~1 m, which matches our bin width.)

### F. App change — render strip

New helper `renderActivityStrip(panelDef, bins, color, height=4)` called
from inside `renderPanel` after the channel polylines. Logic:

- Walks the resampled bool bin array; emits `<rect>` blocks for
  contiguous runs where the value rounds to true.
- Strip placement: at the **bottom of the panel's plot area**, inside the
  existing `clip-path="url(#clip-${def.id})"` so zoom clips correctly.
  Y range: `PAD.top + plotH - 4` to `PAD.top + plotH` (4 px tall).
- Colour:
  - ABS strip on the **brake** panel — `var(--brake)` (red, `#f44336`)
    at 0.85 opacity. Matches "the car helped your braking" visual story.
  - TC strip on the **throttle** panel — `var(--throttle)` (green,
    `#4caf50`) at 0.85 opacity. Mirrors brake side.

These vars are *channel* colours (deliberately not `--session`/`--ref`),
so Feature 1's user-customisable lap colours don't muddy the meaning.

Hook-up via panel definition flags:

```javascript
{ id: 'brake',    ..., activityStrip: { col: 'abs_active', color: 'var(--brake)' } }
{ id: 'throttle', ..., activityStrip: { col: 'tc_active',  color: 'var(--throttle)' } }
```

`renderPanel` checks `def.activityStrip?` and `bins.session_<col>` —
strip omitted if the bin array is missing or all-zero/all-NaN.

### G. App change — tooltip

In `updateCursorPosition`, after the existing `sBrake`/`sThrottle` lookup,
add ABS/TC indicators when active at the cursor bin:

```javascript
const sAbs = currentSessionBins.abs_active?.[binIdx];
const sTc  = currentSessionBins.tc_active?.[binIdx];
const flags = [
  sAbs >= 0.5 ? 'ABS' : null,
  sTc  >= 0.5 ? 'TC'  : null,
].filter(Boolean);
if (flags.length) lines.push(`active: ${flags.join(', ')}`);
```

Reference lap is intentionally *not* shown — flags are session-side; the
user is looking at "where did MY car help me," not the comparison. (Can
extend later if multi-lap.)

### H. Acceptance tests (T5–T8)

- T5: synthetic writer test — round-trip a 2-row Frame with
  `abs_active=True, tc_active=None` → re-read parquet has those exact
  two columns with the right values. (Subprocess into `python -c`.)
- T6: app — load a parquet that *would have* abs/tc (test fixture: take
  the existing 142624Z parquet and synthesise abs/tc columns into a
  copy via pyarrow); compare two laps; assert:
  - `<rect>` strips exist inside the brake panel SVG (`> 0` rects under
    `[data-panel-id="brake"]`).
  - `<rect>` strips exist inside the throttle panel SVG.
  - All strips are inside the panel's `<clipPath>` rect bounds.
- T7: app — load the unmodified 142624Z parquet (no abs/tc columns);
  compare two laps; assert:
  - 0 strips on either panel.
  - No console errors.
  - All other panels render normally (panel count = 8).
- T8: M5 + F1F2 + M6-extras suites still pass.

---

## Feature 3 — TinyPedal deltabest CSV ingest

### A. Format investigation

The TinyPedal install path is not guaranteed to be on this machine. Plan
covers both branches:

1. **If a sample is reachable**: search common TinyPedal locations
   (`%APPDATA%/TinyPedal/deltabest/*.csv`,
   `~/Documents/TinyPedal/deltabest/*.csv`,
   `<TinyPedal repo>/deltabest/*.csv`) and read one. Document the
   actual format (header, units, delimiter) inline in `loadDeltabestCsv`.
2. **Fallback (TinyPedal source review)**: `pip show tinypedal` →
   site-packages; or check the TinyPedal repo on GitHub. The known
   shape (per public TinyPedal documentation) is:

   ```
   # comment / metadata header (optional)
   distance_m, lap_time_s
   0.0,        0.000
   1.0,        0.043
   ...
   ```

   - Comma delimiter.
   - One row per metre (typically) — total rows ≈ track length.
   - First column distance in metres, second column cumulative lap
     time in seconds.
   - Possible header line(s) starting with `#` or `<col>,<col>`.

3. **If neither (15 min cap → BLOCKED.md)**: write
   `m6-test-report/BLOCKED.md` with what was tried and resume after
   user provides a sample. Don't block features 1 + 2 on this.

The implementation parser will be tolerant: skip blank lines and lines
starting with `#`, sniff the first non-blank line for a header (any
non-numeric first token → header), then parse `distance,time` rows.
Reject if either column has fewer than 100 rows.

### B. File picker

- Extend `<input id="file-input" accept=".parquet,.json,.csv" multiple>`.
- In `loadFile(file)`, branch on extension:
  ```javascript
  const ext = file.name.toLowerCase().split('.').pop();
  if (ext === 'json')    return loadSidecar(file);
  if (ext === 'csv')     return loadDeltabestCsv(file);
  /* default: parquet */
  ```

### C. `loadDeltabestCsv(file)` — synthetic store entry

Build an entry shaped exactly like a real parquet entry (so every
existing consumer Just Works):

```javascript
{
  fileName: file.name,
  data: {
    lap_number:      Int32Array,    // all zeros (single synthetic lap)
    lap_time_s:      Float32Array,  // from CSV
    lap_distance_m:  Float32Array,  // from CSV
    speed_kph:       Float32Array,  // derived: 3.6 * Δd/Δt
    // Optional zero-length channels for missing data —
    // existing app already handles `raw.length === 0` (see renderAll).
    throttle_norm: [], brake_norm: [], engine_rpm: [],
    gear: [], steering_norm: [],
    slip_angle_fl_deg: [], slip_angle_fr_deg: [],
    last_sector_1_s: [], last_sector_2_s: [],
    pos_x_m: [], pos_z_m: [],
    abs_active: [], tc_active: [],
  },
  segments: [{ lapNum: 0, start: 0, end: rowCount }],
  hasSlip: false,
  hasSectors: false,
  isDeltabest: true,
  sidecar: {
    schema_version: 'tinypedal-deltabest',
    sim: 'tinypedal',
    track: 'unknown',
    vehicle_name: 'TinyPedal deltabest',
    setup_file_guess: null,
    sample_rate_hz: null,
    row_count: rowCount,
    lap_count: 1,
    in_progress: false,
  },
}
```

### D. Speed derivation

If the CSV provides only `(distance, time)`:

```javascript
for i in 1..n-1:
  ds = d[i] - d[i-1]
  dt = t[i] - t[i-1]
  speed_mps[i] = ds / max(dt, 1e-3)
  speed_kph[i] = speed_mps[i] * 3.6
speed_kph[0] = speed_kph[1]
```

Smooth via a 3-tap moving average to avoid 1 m quantisation noise (the
same reason TinyPedal traces look choppy in our app — uneven spacing in
the source). Document the smoothing in a 1-line comment in the parser
(it's a non-obvious why).

### E. Picker label and Compare button

`formatPickLabel` already reads `entry.sidecar?.vehicle_name`; the
synthetic sidecar above produces:

```
deltabest.csv / Lap 1 #0  3:42.123 · TinyPedal deltabest
```

`rebuildPickers` groups by file — the deltabest CSV becomes its own
`<optgroup>` because each loaded file has its own store key. ★-best-lap
detection only considers `1 < i < total - 1`, so a 1-segment deltabest
just renders without a star. No code change required.

### F. Compare against deltabest

A typical user flow: load a session parquet *and* a deltabest CSV, pick
a session lap from the parquet, deltabest as reference. Renderer:

- Speed panel — both polylines drawn (parquet has speed; deltabest has
  derived speed). ✓
- Throttle / Brake / RPM / Gear / Steering / Slip panels — reference
  trace is empty (zero-length), already handled in `renderAll`:
  `if (!raw || raw.length === 0)` → empty bin array → flat at 0. The
  *reference* polyline becomes a flat line at the bottom for those
  panels, but **only when the deltabest is the reference**. That's
  acceptable for v1 (handoff says "panels with no deltabest data show
  only the session trace") and we'll fix the visual by hiding zero-only
  ref polylines in a small follow-up below.
- **Hide-empty-ref tweak.** In `renderPanel`, if a channel's bin array
  is all-zero / all-NaN, skip drawing its polyline entirely. Cheap
  guard: `binArr.some(v => v !== 0 && isFinite(v))`.
- Δt panel — works because both speed traces exist. ✓
- Sector markers — `deriveSectorDistances` returns null when sector
  columns are missing → no markers. ✓
- Coarse-data warning — depends on the deltabest's median Δd; CSV at
  1 m spacing means median Δd ≈ 1.0, so warning won't fire. ✓
- Circuit map — driven by session-side `pos_x_m`/`pos_z_m`, which is
  the parquet (always loaded as session). Map is fine.

### G. Mixed multi-load

`<input multiple>` already passes all dropped files through `loadFile`
as a `Promise.all`. The user can drop `(parquet, sidecar.json,
deltabest.csv)` in one shot:
- parquet → `loadFile` → store entry
- json → `loadSidecar` → attached to parquet (same stem)
- csv → `loadDeltabestCsv` → its own store entry

No reordering or sequencing changes needed.

### H. Acceptance tests (T9–T12)

The handoff says "fabricate a synthetic CSV in-line in the test (~50
rows of distance,time)" — do that. No real TinyPedal file needed for
the test.

- T9: load synthetic deltabest CSV via the multi-file input → store has
  one entry, picker shows `TinyPedal deltabest` in its label, picker
  has 1 option for that file.
- T10: load 142624Z parquet + synthetic deltabest CSV → pick lap 2 of
  parquet vs deltabest as reference → assert: 8 panels render, speed
  panel has 2 polylines, Δt panel has 1 polyline, no console errors.
- T11: drop a parquet + its sidecar + a deltabest CSV in a single
  multi-select → all three end up in the right places (parquet entry
  has `entry.sidecar` populated, deltabest is a separate entry with the
  synthetic sidecar). 2 store entries, 1 sidecar attached.
- T12: M5 + F1F2 + M6-extras + the new M6 suite all pass.

---

## Steps (in order)

1. **Author this plan** ← we're here.
2. **Feature 1 — colours.** Pickers, defaults block, persistence,
   reset. Smoke-check by hand in browser before tests.
3. **Feature 2 — recorder.** Frame fields, LMU read, rF2 None, schema +
   append. `python -c` round-trip to confirm parquet writes + reads.
4. **Feature 2 — app.** COLUMNS, panel defs, strip renderer, tooltip
   flags, pre-existing-parquet still loads.
5. **Feature 3 — CSV ingest.** Loader branch, parser, synthetic entry,
   picker check by hand.
6. **`scripts/test_m6.js`** — extends, doesn't replace. Includes the
   pyarrow synthetic-fixture step that injects abs/tc columns into a
   throwaway copy of 142624Z, plus the inline synthetic CSV.
7. **Update `.gitignore`** — replace the explicit
   `m4-test-report/`, `m5-test-report/` lines with a glob
   `m*-test-report/` and add `f1f2-test-report/` if not already covered.
8. **Run all four suites** — `node scripts/test_m5.js` → 25/25,
   `node scripts/test_f1f2.js` → 13/13,
   `node scripts/test_m6_extras.js` → 17/17,
   `node scripts/test_m6.js` → all green.
9. **Write `m6-test-report/REPORT.md`** with screenshots and a row per
   assertion. Add note about manual LMU smoke pending.
10. **DESIGN.md §11** — add F5 (colours) / F6 (ABS-TC) / F7 (deltabest
    CSV) "shipped" entries, mark M6 done in §7. **CLAUDE.md** —
    "Current state" mentions abs/tc columns + TinyPedal CSV ingest +
    customisable lap colours.
11. **Commit.**

If any feature hits a real architectural blocker, leave
`m6-test-report/BLOCKED.md` with the question and what was tried and
move on to the others.

---

## Acceptance test summary

| ID  | Feature | Test |
|-----|---------|------|
| T1  | colours | colour picker change → polyline stroke updates |
| T2  | colours | reload page → persisted colour applied + pickers synced |
| T3  | colours | reset button → defaults restored, localStorage cleared |
| T4  | colours | M5 + F1F2 + M6-extras suites still 25/25, 13/13, 17/17 |
| T5  | abs/tc  | recorder writer round-trip with synthetic Frame |
| T6  | abs/tc  | parquet with synthesised abs/tc cols → strips render |
| T7  | abs/tc  | pre-M6 parquet → 0 strips, no errors, panels render |
| T8  | abs/tc  | regression suites pass |
| T9  | csv     | load deltabest CSV → store entry + picker option |
| T10 | csv     | parquet vs deltabest comparison → 8 panels, Δt OK |
| T11 | csv     | mixed multi-load (parquet + json + csv) handled |
| T12 | csv     | regression suites pass |

---

## Notes / scope boundaries

- Feature 1: only `--session` and `--ref` are user-customisable. Other
  CSS vars (channel/state colours) stay default. Multi-lap palette is
  out of scope.
- Feature 2: ABS/TC are session-only; reference lap flags are not shown
  in the strip or tooltip. `mABS`/`mTC` *level* fields exist on the
  same struct (uint8 0..N) — out of scope; would be a separate
  "driver-aid level over time" feature.
- Feature 3: read-only ingest. No round-trip to TinyPedal, no
  auto-discovery, no track-name extraction from the filename even if
  TinyPedal embeds it (we don't trust the format that strongly yet).
