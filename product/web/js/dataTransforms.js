// ── Pure data transformation helpers — no DOM, no store ──────────────────────

/**
 * Parse TinyPedal deltabest CSV text and return derived telemetry arrays.
 * Input format: distance_m, lap_time_s (samples spaced ~9 m apart)
 * Output: data object matching parquet schema + segment definition
 */
export function parseDeltabestCsv(text) {
  const dist = [], time = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const parts = line.split(',');
    if (parts.length < 2) continue;
    const d = parseFloat(parts[0]);
    const t = parseFloat(parts[1]);
    if (!Number.isFinite(d) || !Number.isFinite(t)) continue;
    dist.push(d);
    time.push(t);
  }
  if (dist.length < 10) {
    throw new Error(`only ${dist.length} valid rows`);
  }

  // Derive speed from Δd/Δt. TinyPedal samples are spaced ~9 m apart, so a
  // 3-tap moving average on the differentiation reduces 1 m quantisation
  // noise without smearing the trace.
  const n = dist.length;
  const speedRaw = new Float32Array(n);
  for (let i = 1; i < n; i++) {
    const dd = dist[i] - dist[i - 1];
    const dt = Math.max(time[i] - time[i - 1], 1e-3);
    speedRaw[i] = (dd / dt) * 3.6;  // m/s → km/h
  }
  speedRaw[0] = speedRaw[1];
  const speed = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const a = speedRaw[Math.max(0, i - 1)];
    const b = speedRaw[i];
    const c = speedRaw[Math.min(n - 1, i + 1)];
    speed[i] = (a + b + c) / 3;
  }

  const lapNum = new Int32Array(n);  // all zeros — single synthetic lap
  const lapDist = new Float32Array(dist);
  const lapTime = new Float32Array(time);

  return {
    data: {
      lap_number:        lapNum,
      lap_time_s:        lapTime,
      lap_distance_m:    lapDist,
      speed_kph:         speed,
      throttle_norm:     [],
      brake_norm:        [],
      engine_rpm:        [],
      gear:              [],
      steering_norm:     [],
      slip_angle_fl_deg: [],
      slip_angle_fr_deg: [],
      last_sector_1_s:   [],
      last_sector_2_s:   [],
      pos_x_m:           [],
      pos_z_m:           [],
      abs_active:        [],
      tc_active:         [],
    },
    segments: [{ lapNum: 0, start: 0, end: n }],
    rowCount: n,
  };
}

/**
 * Build sidecar metadata for a TinyPedal deltabest CSV.
 */
export function buildDeltabestSidecar(rowCount) {
  return {
    schema_version: 'tinypedal-deltabest',
    sim: 'tinypedal',
    track: 'unknown',
    vehicle_name: 'TinyPedal deltabest',
    setup_file_guess: null,
    sample_rate_hz: null,
    row_count: rowCount,
    lap_count: 1,
    in_progress: false,
  };
}
