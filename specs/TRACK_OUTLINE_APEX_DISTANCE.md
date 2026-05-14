# Track Outline and Apex Distance Plan

## Goals

1. Record the car's place on track versus configured apexes so the UI can show distance to apex in key turns.
2. Approximate the actual track width around the whole perimeter so the UI can render a track outline from real sim data.

## Background

LMU/rF2 shared memory exposes useful scoring fields per vehicle:

- `mLapDist` — current distance around track in meters.
- `mPathLateral` — signed lateral position relative to the sim path.
- `mTrackEdge` — distance from the sim path to the track edge on the same side as the vehicle.

Wheel telemetry also exposes:

- `mSurfaceType` — dry, wet, grass, dirt, gravel, kerb, special.
- `mTerrainName` — material prefix from the track data.

These channels do not provide complete official boundary geometry, but they are the best telemetry-accessible basis for LMU-native apex and track-width analysis.

---

## Goal A: Record place on track versus apex

### A1. Extend recorder data

Add the following columns to each recorded Parquet row:

- `raw_lap_distance_m`
- `path_lateral_m`
- `track_edge_m`
- `distance_to_track_edge_m`
- `surface_type_fl`
- `surface_type_fr`
- `surface_type_rl`
- `surface_type_rr`
- `terrain_name_fl`
- `terrain_name_fr`
- `terrain_name_rl`
- `terrain_name_rr`

Derived field:

```text
distance_to_track_edge_m = track_edge_m - abs(path_lateral_m)
```

Keep both distance channels:

- `lap_distance_m` — current speed-integrated recorder distance, useful for smooth charts.
- `raw_lap_distance_m` — exact sim scoring distance, useful for joining with path/edge data.

### A2. Create corner/apex annotation files

Create one annotation file per track layout, for example:

```json
{
  "track_id": "circuit-de-spa-francorchamps",
  "layout_id": "default",
  "corners": [
    {
      "id": "t1",
      "name": "La Source",
      "s_start_m": 200,
      "s_end_m": 360,
      "apex_s_m": 285,
      "apex_side": "right"
    }
  ]
}
```

Start with manual annotation. Later, add UI tooling to adjust apex positions visually.

### A3. Compute apex metrics per lap

For each configured corner window:

1. Select samples where `raw_lap_distance_m` is between `s_start_m` and `s_end_m`.
2. Find the sample closest to `apex_s_m`.
3. Find the minimum inside-edge distance near the apex.
4. Compute whether the driver reached the apex early or late.
5. Record surface type/terrain at or near the apex.

Example output:

```text
La Source:
- apex distance: 0.82 m from right edge
- apex timing: 5.4 m late
- surface at apex: dry / kerb / grass
```

### A4. Store derived metrics

Initially compute metrics in-memory for the web UI. If needed, persist them as a sidecar JSON next to the session:

```json
{
  "session": "session_...parquet",
  "lap": 4,
  "corners": [
    {
      "id": "t1",
      "name": "La Source",
      "apex_distance_m": 0.82,
      "apex_timing_error_m": 5.4,
      "surface_type": "kerb"
    }
  ]
}
```

---

## Goal B: Approximate actual track width around the whole perimeter

### B1. Build a width-profile generator

Create a tool that reads recorded Parquet sessions and buckets samples by `raw_lap_distance_m`, for example in 1 m bins.

For each sample:

```text
if path_lateral_m < 0:
  left_width[s_bin] = max(left_width[s_bin], track_edge_m)
else:
  right_width[s_bin] = max(right_width[s_bin], track_edge_m)
```

This learns the sim-reported edge distance on both sides of the path.

### B2. Use calibration laps

To improve coverage, record laps where the driver intentionally samples:

- left edge
- right edge
- kerbs
- normal racing line

The more laps ingested, the better the learned width envelope.

### B3. Smooth and fill gaps

After binning:

- interpolate missing left/right bins
- smooth the width profile over distance
- flag low-confidence bins
- keep sample counts per bin and side

Example output:

```json
{
  "track_id": "circuit-de-spa-francorchamps",
  "layout_id": "default",
  "bin_size_m": 1,
  "samples": [
    {
      "s_m": 0,
      "left_width_m": 7.4,
      "right_width_m": 6.8,
      "left_sample_count": 12,
      "right_sample_count": 9,
      "confidence": 0.92
    }
  ]
}
```

### B4. Reconstruct center/path polyline

Use recorded world positions to reconstruct a drawable sim path:

1. Bucket samples by `raw_lap_distance_m`.
2. Aggregate `pos_x_m` and `pos_z_m` per bin.
3. Prefer clean laps or calibration laps.
4. Smooth the resulting path.

The path should be stored in the same coordinate space as telemetry positions.

### B5. Derive boundaries for rendering

Given a center/path polyline and left/right width profiles:

```text
left_boundary = center_path - normal * left_width
right_boundary = center_path + normal * right_width
```

Render:

- center/path line
- left boundary
- right boundary
- filled track polygon if desired
- telemetry trajectory overlay

---

## Implementation phases

### Phase 1: Recorder schema update

Update:

- `lap_telemetry/recorder/connect.py`
- `lap_telemetry/recorder/writer.py`

Acceptance criteria:

- New Parquet files contain lateral/edge/surface columns.
- Existing recording flow still works.
- Sidecar schema version is bumped.

### Phase 2: Width profile extraction

Add a command such as:

```bash
lap-telemetry track-profile sessions/*.parquet
```

Output:

```text
tracks/<track-id>/<layout-id>/width-profile.json
```

Acceptance criteria:

- Profile contains left/right width bins.
- Profile includes sample counts and confidence.
- Missing sections are explicitly flagged.

### Phase 3: Apex annotation and metrics

Add per-layout apex annotation files and analysis code.

Acceptance criteria:

- For configured corners, reports distance to apex/inside edge per lap.
- Reports early/late apex timing in meters.
- Includes surface/terrain information at apex.

### Phase 4: Track outline rendering

Use the learned center path and width profile to render a full track outline in the web UI.

Acceptance criteria:

- Track map shows approximate full-width outline.
- Telemetry trajectory overlays correctly in sim coordinates.
- Low-confidence outline sections can be visually distinguished.

### Phase 5: Calibration and quality tools

Add diagnostics for profile quality:

- missing bins
- one-sided-only width bins
- low sample count areas
- surface-type overlays
- comparison between laps and learned edges

Acceptance criteria:

- We can tell whether a track profile is trustworthy before using it for apex coaching.

---

## Caveats

`mPathLateral` and `mTrackEdge` are described by rF2-style docs as relative to a very approximate center path. LMU may be better, but this must be validated empirically.

This plan should therefore treat the learned outline as sim-derived and approximate, not as official FIA survey geometry.
