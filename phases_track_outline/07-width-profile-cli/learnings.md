# Learnings — Phase 07 Width Profile CLI

1. **Python `null` ≠ Python `None`.** When building synthetic Parquet fixtures from JavaScript, `JSON.stringify(null)` produces the string `null` which is a `NameError` in Python, not the `None` keyword. The `pyList()` helper maps JS `null`/`undefined` → Python `None` string to avoid this.

2. **hyparquet returns null for missing columns, not undefined.** Rows with no value for a requested column get `null` in the column data array. Our `isValidRow` check uses `Number.isFinite()` which correctly rejects `null` (returns `false`).

3. **Floor-based bin key is simple and sufficient.** `Math.floor(raw_lap_distance_m / binSizeM) * binSizeM` produces correct integer bin keys for the default `bin_size_m=1`. No need for rounding or custom bucket logic at this stage.

4. **path_lateral_m = 0 goes to right bin.** The spec says `if path_lateral_m < 0: left, else: right`, so zero is explicitly right. Test 8 confirms this.

5. **No frontend changes needed.** The entire phase is a Node CLI/helper. `npm run build` produces the same `dist/compare.html` since no web sources changed.