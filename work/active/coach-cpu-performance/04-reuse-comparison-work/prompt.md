# Slice 04 — Reuse invariant comparison work safely

**Status:** 📋 Planned, lower priority, NOT started. Requires explicit selection.

## Goal and expected limit

Reduce repeated reference preparation, subprocess/serialization and unnecessary
Parquet decoding while preserving exact web-pipeline/facts parity. On slice 01's
workload comparison is only ~0.33 CPU-s (about 2.3% of remaining cost); this
cannot achieve 10% of original total CPU by itself. Prioritize it only when
profiling actual race input paths shows a material cost or growing spike.

## Execution

1. Trace actual live lap-flush paths first. Live inputs may already be small
   per-lap shards: do not optimize full-history reads solely because an offline
   replay uses a merged session. Measure race-length growth and cold/warm stages.
2. Profile reference decoding/resampling, Node startup, JSON serialization and
   driver reading separately. Choose the one dominant avoidable repeated cost.
3. Write failing parity/cache-invalidation tests. Implement the simplest bounded,
   per-session reuse or required-column projection justified by that evidence.
   Path-only caching must not return stale reference/model contents after a file
   changes; bound ownership/memory and isolate track/car/layout combinations.
4. Preserve authoritative duration metadata/successor context, stale-frame and
   partial-lap guards, car-aware resolution and stable corner IDs/geometry.
   Cover restarts/reused lap numbers and shard boundaries. Stop for scope
   clarification if those reveal an existing correctness bug; do not quietly
   replace segment-safe selection with a naive lap-number filter.
5. Compare full facts and resampled channels against the current JS pipeline
   across several real tracks/cars and realistic race shards. Do not introduce
   a second, approximately equivalent Python resampling algorithm.
6. Measure whole-event CPU as well as comparison-stage CPU and memory. Report
   the small expected total gain honestly; run feature/full --pw suite/build,
   commit, update handoff/learnings/plan, and stop.

## Acceptance

Exact facts/channel parity, bounded/invalidation-safe reuse and measured gain
on the actual live input shape. No regression for partial laps, changing refs,
record-only mode or optional engine dependencies. A negative profiling result
can retire/defer this option instead of adding an unused cache.

## Non-goals

No coaching semantic changes, track-data edits, TTS optimization, process-worker
rewrite or claims that a fast comparator removes the dominant synthesis cost.
