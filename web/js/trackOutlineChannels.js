// ── Track outline/apex optional telemetry channel helpers ────────────────────

export const TRACK_OUTLINE_CHANNELS = [
  'raw_lap_distance_m',
  'path_lateral_m',
  'track_edge_m',
  'distance_to_track_edge_m',
  'surface_type_fl',
  'surface_type_fr',
  'surface_type_rl',
  'surface_type_rr',
  'terrain_name_fl',
  'terrain_name_fr',
  'terrain_name_rl',
  'terrain_name_rr',
];

export function hasTrackOutlineChannels(data) {
  return !!(
    data &&
    data.raw_lap_distance_m && data.raw_lap_distance_m.length > 0 &&
    data.path_lateral_m && data.path_lateral_m.length > 0 &&
    data.track_edge_m && data.track_edge_m.length > 0
  );
}

export function rawLapDistanceAt(data, index, opts = {}) {
  const raw = data?.raw_lap_distance_m;
  if (raw && Number.isFinite(raw[index])) return raw[index];

  if (opts.allowIntegratedFallback) {
    const integrated = data?.lap_distance_m;
    if (integrated && Number.isFinite(integrated[index])) return integrated[index];
  }

  return null;
}
