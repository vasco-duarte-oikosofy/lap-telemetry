# Learnings — Phase 04.1 Apex Metrics All Corners

- The existing loaded-session `entry` shape is enough for aggregation: use `entry.segments` to preserve displayed lap order and slice the existing column arrays for the Phase 04 one-lap helper.
- Returning an empty `{ status, metrics: [] }` result for not-configured and unavailable cases is simpler for later UI code than returning one null metric per possible pair.
- The aggregator accepts both annotation loader results (`{ status: 'ok', annotations }`) and already-validated annotation objects; this keeps tests and future callers small without adding UI coupling.
- Legacy telemetry must be rejected before per-corner iteration so `lap_distance_m` cannot accidentally influence apex metrics.
