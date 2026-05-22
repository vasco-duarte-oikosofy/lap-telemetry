# Bug: Large Lusail Sessions — "Maximum call stack size exceeded"

## Status

🔍 Investigating — partial fix shipped, root cause identified, recorder fix pending.

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
| `session_20260522T063035Z_lusail-international-circuit_lmu.parquet` | 236,983 | ❌ Fails |
| `session_20260522T075107Z_lusail-international-circuit_lmu.parquet` | 331,175 | ❌ Fails |

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

## Fix shipped (commits c06f9cc, 511d2a7)

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

---

## Root fix still needed — recorder

The app-level fix is defensive. The correct fix is in the recorder so the
problematic columns are never written as long uniform runs in the first place.

**Problem:** The recorder writes `bool(tele_v.mTCActive)` — `False` for every
frame TC is inactive. On a track where TC rarely fires, or for a car with weak
TC calibration, this produces a massive uniform `False` run.

**Fix:** Write `None` (null) when the SHM value is 0, and `True` only when it
is 1:

```python
# product/python/lap_telemetry/recorder/connect.py — in _frame_from_lmu()

# Current:
abs_active=bool(tele_v.mABSActive),
tc_active=bool(tele_v.mTCActive),

# Fixed:
abs_active=True if tele_v.mABSActive else None,
tc_active=True if tele_v.mTCActive else None,
```

Null values are stored in PyArrow's definition-level bitmap (not in the data
pages), so there is no long uniform run in the actual encoded data regardless
of session length or track character. The column stays nullable bool: `True`
= system active, `None` = system not active or not present.

This is a **semantic change**: `False` (system present, not active) collapses
to `None` (not active / not present). In practice the app already renders
`None` and `False` identically in the ABS/TC panels, so there is no visible
regression.

Sessions recorded before this fix will still load correctly via the app-level
isolation — they just won't show ABS/TC data if the run length exceeded the
threshold.

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
| `dev/scripts/test_uniform_rle_load.js` | Regression test |
| `dev/scripts/parquet-fixture-uniform-rle.parquet` | Test fixture |
| `package.json` | Test wired into full suite |

## Next action

Implement the recorder fix in `connect.py` and add a test that verifies
`tc_active` is written as `None` (not `False`) for inactive frames.
