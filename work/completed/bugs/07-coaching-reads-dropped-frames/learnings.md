# Bug 07 Learnings

## What surprised us

1. **LiveBus is synchronous but now analysis is async** — Before this fix, `_on_lap_completed` ran on whatever thread the bus subscriber callback fired on (synchronous for LiveBus, worker for QueuedBus). Now it submits to a ThreadPoolExecutor, so even LiveBus-based tests need to wait for the pool to complete before checking results. The `test_live_after_lap_spoken_summary.py` test needed updating: it now sets `COACH_PARQUET_TIMEOUT_S=0.01` to avoid a 10s wait and adds a pool-drain step before asserting utterances.

2. **SessionWriter shard path is ephemeral** — The `on_lap_flushed` callback fires with the shard `.partN.parquet` path, but `close()` merges shards into a final `.parquet` and deletes the shards. Tests that verify the path must run before `close()`, or only check that the path has the right extension.

3. **TrackCoachingModel requires `schema_version` and `layout_id`** — Creating a model with just `track_id` and `lap_length_m` fails with a `TypeError`. All test fixtures need these fields.

4. **StraightZone requires `id` field** — Similar to above, the dataclass has an `id` field that tests need to provide.

5. **compare_laps `lap_number` filter** — Adding the `lap_number` parameter to `compare_laps()` was clean — it filters the current table with a PyArrow boolean mask before running the rest of the pipeline. No changes to the JS pipeline needed; it operates on the pre-filtered data.

6. **Parquet flush timing** — The `_wait_for_parquet()` method uses a 10s timeout (configurable via `COACH_PARQUET_TIMEOUT_S` env var). In practice, `SessionWriter.flush_shard()` is called every 30s or at session boundaries, so the wait should resolve quickly when the recorder is running. The 10s is a safety net for edge cases.

## Key decisions

- **ThreadPoolExecutor(max_workers=1)** ensures sequential lap analysis (no race conditions between consecutive laps).
- **Corner-exit analysis stays on the pool thread** but uses live frames, not Parquet — this preserves sub-second latency and avoids waiting for a flush.
- **The `on_lap_flushed` callback is wired through `QueuedBus.on_lap_flushed`** rather than directly to avoid tight coupling between `SessionWriter` and `CoachTap`. The recorder sets `bus.on_lap_flushed = tap.notify_parquet_flushed` when creating the writer.

## Deferred TODOs

- The 30s `_FLUSH_INTERVAL_S` in `record.py` means worst-case 30s added latency for after-lap summaries. A future improvement could flush on lap boundary detection inside the recorder loop.
- Consider reducing the shard flush interval during live coaching sessions (e.g., to 5s when the coach is active).