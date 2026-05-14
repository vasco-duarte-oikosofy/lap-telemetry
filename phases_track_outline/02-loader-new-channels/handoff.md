# Handoff — Phase 02 Loader New Channels

State on disk:

- `web/js/ui.js`
  - Parquet loader now requests all `TRACK_OUTLINE_CHANNELS` in addition to existing chart/map columns.
  - The new fields are stored read-only in the existing `entry.data` session shape.
  - Missing outline columns remain empty arrays for legacy sessions.
- `web/js/trackOutlineChannels.js`
  - Added `warnInvalidTrackOutlineSamples(data, label)` for dev-console warnings on `NaN` numeric outline values and negative `track_edge_m`.
- `web/js/debugHooks.js`
  - Added `window.__getSessionData(key)` for Playwright assertions of loaded browser-side session data.
- `scripts/test_track_outline_loader_channels.js`
  - Verifies exact browser-loaded values for every Phase 01 channel.
  - Verifies legacy sessions leave missing outline columns empty and do not synthesize `raw_lap_distance_m` from `lap_distance_m`.
  - Verifies legacy compare rendering keeps the existing structural panel labels/count and shows no new outline UI labels.
- `npm test` includes the Phase 02 loader test.
- `dist/compare.html` was rebuilt with `npm run build`.

Feature flags live: none. This phase is read-only in browser memory and intentionally adds no panels, chart traces, map layers, labels, or apex metrics.

Deferred to Phase 03:

- Apex annotation files, loader, and validator.
