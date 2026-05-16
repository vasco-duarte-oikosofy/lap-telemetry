# Handoff — Phase 01 Recorder Track-Edge Channels

State on disk:

- `lap_telemetry/recorder/connect.py`
  - `Frame` now has optional outline/apex telemetry fields.
  - LMU and rF2 connection reads now populate:
    - raw sim `mLapDist` as `raw_lap_distance_m`
    - `mPathLateral`
    - `mTrackEdge`
    - derived distance to edge
    - per-wheel `mSurfaceType`
    - per-wheel `mTerrainName`
  - Missing shared-memory attributes map to `None`.
- `lap_telemetry/recorder/writer.py`
  - Parquet schema includes all Phase 01 fields.
  - Writer derives `distance_to_track_edge_m` from lateral/edge fields.
  - New sidecars use `schema_version: "2"`.
- `scripts/test_track_outline_recorder_channels.js`
  - Verifies schema fields are present and nullable.
  - Verifies positive and negative lateral distance-to-edge derivation.
  - Verifies missing new fields write nulls.
  - Verifies sidecar schema version is bumped to `2`.
- `npm test` now includes the Phase 01 recorder test.
- `phases_track_outline/PLAN` marks this phase DONE.
- `phases_track_outline/CURRENT` is `02-loader-new-channels`.

Feature flags live: none. Recorder output changed for newly recorded sessions; existing sessions remain compatible through Phase 00 tests.

Deferred to Phase 02:

- Expose these columns in the browser/session loader read-only.
- Keep existing panels visually unchanged.
