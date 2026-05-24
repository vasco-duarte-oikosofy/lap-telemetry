# Bug: Large Lusail Sessions — "Maximum call stack size exceeded"

## Status

Resolved. App-level isolation fix shipped; recorder fix shipped. Both covered by tests.

---

## Symptom

Loading certain Lusail session parquet files in `product/dist/compare.html` fails with:

```
Failed to load session_20260522T075107Z_lusail-international-circuit_lmu.parquet:
Maximum call stack size exceeded
```

---

## Sessions

| Session | Rows | Loads? |
|---|---|---|
| `session_20260522T062054Z_lusail-international-circuit_lmu.parquet` | 28,714 | ✅ OK |
| `session_20260520T160300Z_autodromo-nazionale-monza_lmu.parquet` | 354,736 | ✅ OK |
| `session_20260522T063035Z_lusail-international-circuit_lmu.parquet` | 236,983 | ✅ Fixed |
| `session_20260522T075107Z_lusail-international-circuit_lmu.parquet` | 331,175 | ✅ Fixed |

---

## Root cause

hyparquet expands RLE-encoded column runs using JavaScript spread:
`result.push(...expandedRun)` — or equivalent internally. When a column has a
single run exceeding ~125,000–198,000 identical values, the spread argument
list overflows the JS call stack and throws `RangeError: Maximum call stack
size exceeded`.

### Why Lusail and not Monza?

The overflow threshold appears to be between **120k and 199k** frames of the
same value. Monza sessions stay just under it; long Lusail sessions exceed it.

Key max-run lengths across the four test sessions:

| Session | `terrain_name_fl` max run | `tc_active` max run |
|---|---|---|
| Lusail 062054Z (OK) | 1,993 | 28,714 |
| Monza 160300Z (OK) | 117,123 | 120,391 |
| Lusail 063035Z (FAILS) | 198,637 | 201,095 |
| Lusail 075107Z (FAILS) | 229,673 | 230,437 |

Lusail has very uniform surface coverage (almost entirely `ROAD` with no kerb
or run-off zones). The DKR-4 car at Lusail also rarely triggers TC, producing
long uniform `tc_active=False` stretches. Both columns exceed the overflow
threshold in the long sessions.

`abs_active` is all-False in all sessions (car has no ABS) but uses plain
boolean RLE encoding, which hyparquet handles without spread — so it doesn't
trigger the overflow regardless of run length.

---

## What is NOT the cause

- File size or total row count alone — Monza 354k rows loads fine.
- `abs_active` — all-False in Monza too (354k run), no overflow.
- `tc_active` being True sometimes — that breaks up the False runs and keeps
  them below the threshold (Monza TC fires more than Lusail TC).

---

## App-level fixes

There were two independent spread-overflow sites in the app.

### 1. hyparquet column read (commits c06f9cc, 511d2a7)

`terrain_name_*`, `abs_active`, and `tc_active` are now loaded in isolated
per-column try/catch calls inside `loadFile` (product/web/js/ui.js). A failure
on any of them emits a console warning and leaves the column empty; the main
columns (speed, brake, throttle, lap timing, position) are unaffected.

```javascript
// product/web/js/ui.js — inside loadFile()
for (const col of isolatedCols) {
  try {
    const { data: cd } = await readColumns(file, [col]);
    if (cd[col] && cd[col].length > 0) data[col] = cd[col];
  } catch (e) {
    console.warn(`${file.name}: column '${col}' skipped (hyparquet stack overflow on long uniform RLE run)`);
  }
}
```

Regression test: `dev/scripts/test_uniform_rle_load.js` + fixture
`dev/scripts/parquet-fixture-uniform-rle.parquet`.

### 2. `rebuildPickers` / `formatPickLabel` spread (discovered during verification)

After column reads succeeded, the load still crashed in `rebuildPickers` at:

```javascript
const dur = sliceTimes.length ? Math.max(...sliceTimes) : 0;
```

`sliceTimes` is `lap_time_s` values for one lap segment. When a session has a
large lap (Lusail 075107Z laps reach ~19k frames each), this spread also
overflows. The same pattern existed in `utils.js` (`formatPickLabel`).

Fixed in `pickers.js` and `utils.js` by replacing spread with reduce:

```javascript
const dur = sliceTimes.length ? sliceTimes.reduce((a, b) => b > a ? b : a, -Infinity) : 0;
```

Verified: `session_20260522T075107Z` now loads as **331,175 rows · 17 laps** with no errors.

---

## Recorder fix (shipped)

`connect.py` line 269–270 changed from `bool(tele_v.mABS/TCActive)` to
`True if tele_v.mABS/TCActive else None`. Null values go into PyArrow's
definition-level bitmap, not the data pages — no long uniform run regardless
of session length. `True` = system active, `None` = not active / not present.

Sessions recorded before this fix load via the app-level isolation (ABS/TC
panels will be empty if the run exceeded the overflow threshold).

---

## Open questions

1. What is the exact overflow threshold in V8 for spread argument count? The
   data pins it between 120k and 199k; the actual limit may be 131,072 (2^17)
   or 125,000. Confirm by testing with a synthetic fixture of known size.
2. Is there a hyparquet upstream fix available, or is spread in RLE expansion
   a known limitation of v1? Worth filing an issue.
3. Should `terrain_name_*` also be changed to write `None` when the terrain is
   the default surface, or is the app-level isolation sufficient there?

---

## Files touched

| File | Change |
|---|---|
| `product/web/js/ui.js` | Isolated load for `abs_active`, `tc_active`, `terrain_name_*` |
| `product/dist/compare.html` | Rebuilt |
| `dev/scripts/test_uniform_rle_load.js` | App-side regression test (fixture-based) |
| `dev/scripts/parquet-fixture-uniform-rle.parquet` | Test fixture |
| `package.json` | Test wired into full suite |
| `product/python/lap_telemetry/recorder/connect.py` | Recorder fix (None instead of False) |
| `dev/scripts/test_recorder_nullable_bool.py` | Recorder test (null round-trip via SessionWriter) |
| `product/web/js/pickers.js` | Replace `Math.max(...sliceTimes)` with reduce |
| `product/web/js/utils.js` | Replace `Math.max(...sliceTimes)` with reduce |
