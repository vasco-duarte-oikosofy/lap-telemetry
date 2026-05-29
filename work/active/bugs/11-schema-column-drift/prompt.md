# Bug 11: Schema column drift — duplicated column lists across writer, coach, and JS

## Problem

Every time a new column is added to the Parquet schema (`writer.py` `_SCHEMA`), the
same column must be manually added in several other files. There is no shared
mechanism that enforces completeness, so omissions are only discovered at runtime —
sometimes as a hard crash, sometimes as a silent data miss.

We already hit this once: bug 10b added 4 `scoring_*` columns and broke the coach
pipeline on the first live session because `frames_to_parquet.py` had its own
hand-maintained column dict that wasn't updated (fixed in `641f827`).

## Two distinct risk categories

### Category A — Schema-writer duplicates (crash risk)

Files that **build a Parquet table containing ALL schema columns**. If a column is in
`_SCHEMA` but absent from the file's column dict, `pa.table(columns, schema=_SCHEMA)`
raises `KeyError` immediately.

| File | What it does | Status |
|---|---|---|
| `product/python/lap_telemetry/recorder/writer.py` | **Source of truth** — `_SCHEMA` + `SessionWriter.append()` | ✅ authoritative |
| `product/python/lap_telemetry/coach/frames_to_parquet.py` | Builds identical table from live `Frame` list | ✅ fixed in `641f827` — still a manual list |

`frames_to_parquet.py` still has the structural problem: it imports `_SCHEMA` but
hand-writes its own column lists and dict. The fix landed, but the next schema change
will break it again unless the file is made to derive columns from `_SCHEMA`
dynamically instead of enumerating them.

### Category B — Column-load gates (silent-miss risk)

Files that declare **which columns to request** from hyparquet when loading a Parquet
file. Columns absent from this list are never loaded into the app — no error is raised,
the data is simply unavailable.

| File | Export / constant | Used by |
|---|---|---|
| `product/web/js/panelConfig.js` | `COLUMNS` array (17 entries) | `main.js` → `readColumns()` in `pipeline.js` |

`pipeline.js:readColumns()` already logs `"columns absent in schema"` for columns
listed in `COLUMNS` but absent from the file — but has no mechanism to warn about the
reverse (column in file, not listed in `COLUMNS`, so never loaded).

New display-relevant columns (e.g. the `scoring_*` fields if we ever want to show
them, or any future channel) must be manually added to `panelConfig.js` `COLUMNS` to
be loadable by the app.

## Scope

This is an **audit + DRY slice**. The goals are:

1. **Audit Python** — confirm no other file builds a full Parquet table from `Frame`
   objects outside of `writer.py` and `frames_to_parquet.py`.

2. **Fix `frames_to_parquet.py` structurally** — eliminate the hand-written column
   list by deriving columns from `_SCHEMA` and `Frame.__dataclass_fields__` so the
   function never drifts. The column dict should be built as:
   ```python
   columns = {f.name: [getattr(frame, f.name) for frame in frames] for f in _SCHEMA}
   ```
   (with the `distance_to_track_edge_m` special-case preserved).

3. **Document `panelConfig.js` COLUMNS** — add a comment making it clear that any
   column needed by the app UI must be listed here. Not a code change unless a
   currently-useful column is missing.

4. **Add a guard test** — extend `tests/test_bug10b.py` (or a new
   `tests/test_schema_completeness.py`) with a test that asserts
   `frames_to_parquet` produces a table whose column set exactly matches `_SCHEMA`
   field names, so future schema additions fail the test rather than failing at
   runtime.

## Non-goals

- Do not change `SessionWriter`, `_SCHEMA`, or any column values.
- Do not add or remove columns from `panelConfig.js` `COLUMNS` unless one is clearly
  missing and needed by an existing panel.
- Do not refactor `lap_comparator.py`, `fuel_facts.py`, `summary.py`, or JS panel
  definitions — those are normal column consumers, not schema-writer duplicates.

## Acceptance

- `frames_to_parquet.py` contains no hand-written list of column names; all columns
  are derived from `_SCHEMA`.
- A test asserts that `frames_to_parquet([frame])` output schema == `_SCHEMA` field
  names.
- `panelConfig.js` has a comment explaining the COLUMNS contract.
- `pytest tests/` passes.
