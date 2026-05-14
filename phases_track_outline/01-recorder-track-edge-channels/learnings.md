# Learnings — Phase 01 Recorder Track-Edge Channels

- LMU and rF2 vendored shared-memory structs both expose `mPathLateral`, `mTrackEdge`, wheel `mSurfaceType`, and wheel `mTerrainName` with matching names.
- The safest writer contract is to derive `distance_to_track_edge_m` at append time from `track_edge_m - abs(path_lateral_m)`, so tests do not rely on callers precomputing it.
- Existing recorder tests instantiate `Frame` directly, so new fields must be optional dataclass defaults to preserve old construction sites.
