# Learnings — Bug 17

- `pyarrow.parquet.read_table()` imported the dataset path and emitted noisy NumPy/pandas compatibility warnings in this environment, even though it exited 0. `pyarrow.parquet.ParquetFile(...).read(columns=...)` reads the same columns cleanly for this regression test.
- The real Bahrain Outer lap 19 effective max distance after dropping stale boundary frames is about `2433m`, slightly higher than the prompt's rough `2416m`, but still far below the completion threshold.
