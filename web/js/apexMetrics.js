// ── Apex metric calculation for one lap and one configured corner ────────────

function nullMetric(corner, lap) {
  return {
    corner_id: corner?.id ?? null,
    corner_name: corner?.name ?? null,
    lap,
    apex_distance_m: null,
    apex_timing_error_m: null,
    surface_type: null,
    terrain_name: null,
    sample_s_m: null,
  };
}

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function valueAt(values, index) {
  if (!values || !isFiniteNumber(values[index])) return null;
  return values[index];
}

function inferLap(data, explicitLap) {
  if (explicitLap !== undefined) return explicitLap;
  const laps = data?.lap_number;
  if (laps && laps.length > 0 && laps[0] != null) return laps[0];
  return null;
}

function selectedInsideEdgeDistance(data, index) {
  const recordedDistance = valueAt(data?.distance_to_track_edge_m, index);
  if (recordedDistance !== null) return recordedDistance;

  const lateral = valueAt(data?.path_lateral_m, index);
  const edge = valueAt(data?.track_edge_m, index);
  if (lateral === null || edge === null) return null;
  return edge - Math.abs(lateral);
}

function closestSampleIndex(data, corner) {
  const rawDistances = data?.raw_lap_distance_m;
  if (!rawDistances || rawDistances.length === 0) return null;

  let bestIndex = null;
  let bestDelta = Infinity;
  for (let i = 0; i < rawDistances.length; i++) {
    const s = rawDistances[i];
    if (!isFiniteNumber(s)) continue;
    if (s < corner.s_start_m || s > corner.s_end_m) continue;
    const delta = Math.abs(s - corner.apex_s_m);
    if (delta < bestDelta) {
      bestDelta = delta;
      bestIndex = i;
    }
  }
  return bestIndex;
}

export function computeApexMetricForLap(data, corner, opts = {}) {
  const lap = inferLap(data, opts.lap);
  const empty = () => nullMetric(corner, lap);
  if (!data || !corner) return empty();

  const index = closestSampleIndex(data, corner);
  if (index === null) return empty();

  const sampleS = valueAt(data.raw_lap_distance_m, index);
  const apexDistance = selectedInsideEdgeDistance(data, index);
  if (sampleS === null || apexDistance === null) return empty();

  return {
    corner_id: corner.id,
    corner_name: corner.name,
    lap,
    apex_distance_m: apexDistance,
    apex_timing_error_m: sampleS - corner.apex_s_m,
    surface_type: null,
    terrain_name: null,
    sample_s_m: sampleS,
  };
}
