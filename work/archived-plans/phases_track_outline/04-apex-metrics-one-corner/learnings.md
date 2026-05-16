# Learnings — Phase 04 Apex Metrics One Corner

- The loaded-session shape from Phase 02 is already enough for a pure metric helper: column arrays in `data` plus a validated Phase 03 corner object.
- `distance_to_track_edge_m` should be preferred when present because it is recorder-derived and avoids recomputing from optional fields in browser code.
- The safest unavailable behavior is to return the normal ApexMetric identity fields with all computed metric fields set to `null`; this keeps callers simple and avoids exceptions for legacy sessions.
- No UI wiring was needed for this phase, but `features.apexMetrics` is now exposed with a default of `false` for later delivery switches.
