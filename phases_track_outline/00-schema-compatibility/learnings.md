# Learnings — Phase 00 Schema Compatibility

- The browser loader already tolerates unknown future Parquet columns because it requests only known columns via `readColumns()`.
- A small pure helper was still useful to pin the raw-distance fallback contract before apex/outline analysis exists.
- Synthetic Parquet fixtures can be generated in the Node test via `pyarrow`, matching the pattern used by existing M6 tests.
