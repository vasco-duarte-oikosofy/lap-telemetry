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

function optionalValueAt(values, index) {
  if (!values) return null;
  const value = values[index];
  if (value == null) return null;
  if (typeof value === 'number' && !Number.isFinite(value)) return null;
  if (typeof value === 'string' && value.length === 0) return null;
  return value;
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

function apexSideFields(corner, prefix) {
  if (corner?.apex_side === 'left') return [`${prefix}_fl`, `${prefix}_rl`];
  if (corner?.apex_side === 'right') return [`${prefix}_fr`, `${prefix}_rr`];
  return [];
}

function apexSideValue(data, corner, index, prefix) {
  for (const field of apexSideFields(corner, prefix)) {
    const value = optionalValueAt(data?.[field], index);
    if (value !== null) return value;
  }
  return null;
}

function apexSurfaceTerrain(data, corner, index) {
  return {
    surface_type: apexSideValue(data, corner, index, 'surface_type'),
    terrain_name: apexSideValue(data, corner, index, 'terrain_name'),
  };
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

  const surfaceTerrain = apexSurfaceTerrain(data, corner, index);
  return {
    corner_id: corner.id,
    corner_name: corner.name,
    lap,
    apex_distance_m: apexDistance,
    apex_timing_error_m: sampleS - corner.apex_s_m,
    surface_type: surfaceTerrain.surface_type,
    terrain_name: surfaceTerrain.terrain_name,
    sample_s_m: sampleS,
  };
}

function okResult(metrics) {
  return { status: 'ok', metrics, reason: null };
}

function emptyResult(status, reason = null) {
  return { status, metrics: [], reason };
}

function normalizeAnnotations(annotationInput) {
  if (!annotationInput) return { status: 'not_configured', annotations: null };
  if (annotationInput.status && annotationInput.status !== 'ok') return annotationInput;
  if (annotationInput.status === 'ok') return annotationInput;
  return { status: 'ok', annotations: annotationInput };
}

function hasValues(values) {
  return !!values && values.length > 0;
}

function telemetryUnavailableReason(data) {
  if (!hasValues(data?.raw_lap_distance_m)) return 'missing raw_lap_distance_m';
  if (hasValues(data.distance_to_track_edge_m)) return null;
  if (hasValues(data.path_lateral_m) && hasValues(data.track_edge_m)) return null;
  return 'missing edge distance inputs';
}

function sliceData(data, start, end) {
  const lapData = {};
  for (const [key, values] of Object.entries(data || {})) {
    if (values && typeof values.slice === 'function') {
      lapData[key] = values.slice(start, end);
    } else {
      lapData[key] = values;
    }
  }
  return lapData;
}

export function computeApexMetricsForSession(entry, annotationInput) {
  const normalized = normalizeAnnotations(annotationInput);
  if (normalized.status !== 'ok') return emptyResult(normalized.status, null);

  const data = entry?.data;
  const reason = telemetryUnavailableReason(data);
  if (reason) return emptyResult('unavailable', reason);

  const corners = normalized.annotations?.corners || [];
  const segments = entry?.segments || [];
  const metrics = [];
  for (const seg of segments) {
    const lapData = sliceData(data, seg.start, seg.end);
    for (const corner of corners) {
      metrics.push(computeApexMetricForLap(lapData, corner, { lap: seg.lapNum }));
    }
  }
  return okResult(metrics);
}
