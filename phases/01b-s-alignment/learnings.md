# Phase 01b — Learnings

- **Binary search on Float64Array vs Array**: both work identically for bracketing, but keeping raw arrays as `Float64Array` avoids type surprise when importing from JS modules.
- **Raw data must be kept alive**: the resampled `currentTrackX/Y` is indexed by integer distance, which is lossy for original sample positions. Keeping `sKeep`-mapped raw arrays is necessary for `sLookup` to interpolate correctly in the corners.
- **Dev-only flags should not appear in production UI**: `devFeatures` is a separate object from `features` so the feature-flag dropdown only shows user-facing toggles.
- **Monotonicity check as assertion vs silent fix**: the spec asked for a hard-fail "loudly in dev." Gating the `throw` behind `devMapSAlignmentDebug` means production never crashes, while tests can verify the assertion fires by toggling the flag on.
- **ResizeObserver closures need the raw data too**: storing `currentLapARaw`/`currentLapBRaw` at module level lets the resize callback rebuild the lap objects without recomputing `sKeep`/`rKeep`.
