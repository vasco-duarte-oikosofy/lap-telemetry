# Handoff — Phase 00 Schema Compatibility

State on disk:

- Added `web/js/trackOutlineChannels.js` with:
  - `TRACK_OUTLINE_CHANNELS`
  - `hasTrackOutlineChannels(data)`
  - `rawLapDistanceAt(data, index, { allowIntegratedFallback })`
- Added `scripts/test_track_outline_schema_compat.js` and included it in `npm test`.
- The test covers:
  - legacy-shaped data without outline channels
  - future-shaped data with all outline/apex recorder channels
  - no implicit `lap_distance_m` fallback when `raw_lap_distance_m` is missing
  - explicit fallback only when `allowIntegratedFallback: true`
  - browser loading of synthetic legacy and future Parquet fixtures with no page/console errors
- Marked `00-schema-compatibility` DONE in `phases_track_outline/PLAN`.
- Set `phases_track_outline/CURRENT` to `01-recorder-track-edge-channels`.

Feature flags live: none. This phase adds tests and a pure helper only; no rendered UI or recorder output changed.

Deferred to Phase 01:

- Add the recorder fields to `lap_telemetry/recorder/connect.py` and `writer.py`.
- Bump the recorder sidecar/schema version.
