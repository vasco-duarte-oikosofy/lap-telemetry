// ── Data pipeline module ─────────────────────────────────────────────────────
// Pure computation functions for loading, resampling, and processing telemetry.
// No DOM access, no global state — all functions are pure or async-pure.

// ── Constants ─────────────────────────────────────────────────────────────────

export const PARTIAL_DIST_FRAC = 0.95;  // maxD must be ≥ 95% of trackLen
export const PARTIAL_DUR_FRAC  = 0.5;   // duration must be ≥ 50% of median complete-lap dur
export const ROLLING_DIST_M    = 50;    // |minD| at the first frame may be up to ±50 m

// ── File I/O ──────────────────────────────────────────────────────────────────

export function fileToAsyncBuffer(file) {
  return {
    byteLength: file.size,
    slice: async (start, end) => {
      return await file.slice(start, end).arrayBuffer();
    },
  };
}

export async function readColumns(file, columns) {
  const result = Object.fromEntries(columns.map(c => [c, []]));
  const asyncBuffer = fileToAsyncBuffer(file);

  // Discover which requested columns actually exist in this file
  const { parquetMetadataAsync } = await import('https://cdn.jsdelivr.net/npm/hyparquet@1/+esm');
  const meta = await parquetMetadataAsync(asyncBuffer);
  const schemaNames = new Set(
    meta.schema.flatMap(s => s.name ? [s.name] : [])
  );
  const availableCols = columns.filter(c => schemaNames.has(c));
  const missingCols   = columns.filter(c => !schemaNames.has(c));
  if (missingCols.length) {
    console.log(`readColumns: columns absent in schema: ${missingCols.join(', ')}`);
  }

  // hyparquet v1 onChunk: called once per column (or per column per row-group)
  // chunk = { columnName, columnData: TypedArray, rowStart, rowEnd }
  const { parquetRead } = await import('https://cdn.jsdelivr.net/npm/hyparquet@1/+esm');
  const { compressors } = await import('https://cdn.jsdelivr.net/npm/hyparquet-compressors@1/+esm');
  await parquetRead({
    file: fileToAsyncBuffer(file),
    compressors,
    columns: availableCols,
    onChunk({ columnName, columnData }) {
      if (Object.prototype.hasOwnProperty.call(result, columnName)) {
        for (let i = 0; i < columnData.length; i++) {
          result[columnName].push(columnData[i]);
        }
      }
    },
  });

  return { data: result, missingCols };
}

// ── Segment builder ───────────────────────────────────────────────────────────

export function buildSegments(lapNumbers) {
  if (!lapNumbers.length) return [];
  const segs = [];
  let prev = lapNumbers[0], start = 0;
  for (let i = 1; i < lapNumbers.length; i++) {
    if (lapNumbers[i] !== prev) {
      segs.push({ lapNum: prev, start, end: i });
      prev = lapNumbers[i];
      start = i;
    }
  }
  segs.push({ lapNum: prev, start, end: lapNumbers.length });
  return segs;
}

// Annotate each segment with the distance window it actually covered and the
// lap_time_s it reached, then flag laps that don't look like a clean racing
// lap. Three rules, all purely data-driven (no per-track config):
//   - partial (distance):  the car never reached close to the end of the lap
//                          (truncated by pit-in, parked, or recorder stopped).
//   - partial (duration):  the lap_time_s clock barely advanced — typically
//                          the "ESC a few metres past the finish line" case
//                          where the F4 distance integrator may report near-
//                          full distance from a stale anchor, but the time
//                          counter shows the lap was abandoned almost
//                          immediately. The reference is the median duration
//                          of complete-distance non-rolling laps in the same
//                          file, so the threshold self-calibrates per-track.
//   - rolling:             the car wasn't near the start/finish line at the
//                          first frame (rolling-start formation lap, or
//                          recorder started mid-lap, or race-restart segment).
// trackLen estimate = the longest maxD seen across all segments in this file.
export function annotateSegments(segments, distances, lapTimes) {
  if (!segments.length) return;
  let trackLen = 0;
  for (const seg of segments) {
    let mn = Infinity, mx = -Infinity, mt = 0;
    for (let i = seg.start; i < seg.end; i++) {
      const d = distances[i];
      if (Number.isFinite(d)) {
        if (d < mn) mn = d;
        if (d > mx) mx = d;
      }
      const t = lapTimes ? lapTimes[i] : null;
      if (Number.isFinite(t) && t > mt) mt = t;
    }
    seg.minDist = isFinite(mn) ? mn : 0;
    seg.maxDist = isFinite(mx) ? mx : 0;
    seg.duration = mt;
    if (seg.maxDist > trackLen) trackLen = seg.maxDist;
  }
  // Reference duration: median over candidates that look like real flying laps
  // (full distance + clean start). Falls back to 0 when no candidates exist —
  // in which case the duration check is skipped to avoid false positives.
  const candidateDurs = segments
    .filter(s => s.maxDist >= trackLen * PARTIAL_DIST_FRAC && Math.abs(s.minDist) <= ROLLING_DIST_M)
    .map(s => s.duration)
    .filter(d => d > 0)
    .sort((a, b) => a - b);
  const medDur = candidateDurs.length
    ? candidateDurs[Math.floor(candidateDurs.length / 2)]
    : 0;
  const durFloor = medDur * PARTIAL_DUR_FRAC;
  for (const seg of segments) {
    const distTruncated = seg.maxDist < trackLen * PARTIAL_DIST_FRAC;
    const durTruncated  = durFloor > 0 && seg.duration > 0 && seg.duration < durFloor;
    seg.partial = distTruncated || durTruncated;
    seg.rolling = Math.abs(seg.minDist) > ROLLING_DIST_M;
    seg.fastest = false;
  }
  // Fastest-lap labelling runs *after* partial/rolling so the ★ can never land
  // on a flagged segment. A clean lap is one that's neither partial nor
  // rolling-start; the fastest among those gets the star.
  let bestIdx = -1, bestDur = Infinity;
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    if (seg.partial || seg.rolling) continue;
    if (seg.duration > 0 && seg.duration < bestDur) {
      bestDur = seg.duration;
      bestIdx = i;
    }
  }
  if (bestIdx >= 0) segments[bestIdx].fastest = true;
}

// ── Resampling & interpolation ────────────────────────────────────────────────

export function interpAt(xs, ys, x) {
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
  let lo = 0, hi = xs.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= x) lo = mid; else hi = mid;
  }
  if (xs[hi] === xs[lo]) return ys[lo];
  const t = (x - xs[lo]) / (xs[hi] - xs[lo]);
  return ys[lo] + t * (ys[hi] - ys[lo]);
}

export function resample(distances, values, maxDist) {
  const n = distances.length;
  if (!n) return new Float64Array(maxDist + 1);
  // Sort by distance; stable tie-break by frame index preserves time order within equal-distance clusters
  const idx = Array.from({ length: n }, (_, i) => i);
  idx.sort((a, b) => (distances[a] - distances[b]) || (a - b));
  const xs = idx.map(i => distances[i]);
  const ys = idx.map(i => values[i]);
  const bins = new Float64Array(maxDist + 1);
  for (let bin = 0; bin <= maxDist; bin++) bins[bin] = interpAt(xs, ys, bin);
  return bins;
}

// ── Δt computation ────────────────────────────────────────────────────────────

// Δt(d) = lap_time_s_session(d) − lap_time_s_ref(d), in milliseconds.
// Read directly from the recorder's sim-clock-derived `lap_time_s` column at
// each 1 m bin. Bypasses the F4 distance over-count that previously surfaced
// as a phantom ~60 ms asymmetry vs the real lap-time delta (see
// work/archived-plans/rca-deltat-phantom-error.md and docs/DESIGN.md §4.2).
export function computeDeltaT(sessionLapTime, refLapTime) {
  const len = Math.min(sessionLapTime.length, refLapTime.length);
  const dt = new Float64Array(len);
  for (let i = 0; i < len; i++) dt[i] = (sessionLapTime[i] - refLapTime[i]) * 1000;
  return dt;
}

// Drop the SHM lap-boundary artifact frame from a segment slice. The sim
// updates `mLapNumber` one tick before resetting `mLapDist`/`mLapStartET`,
// so the first frames of every recorded lap can carry the previous lap's
// end-of-pit-straight distance and a tiny near-zero `lap_time_s`. Filter:
// drop frames where lap_time_s < 0.5 s AND lap_distance_m > trackLen × 0.5.
// A real frame at d > trackLen × 0.5 cannot have t < 0.5 s — that would
// require covering > halfTrack metres in under half a second.
export function computeKeepIndices(lapTime, lapDist, start, end, trackLen) {
  const halfTrack = trackLen * 0.5;
  const keep = [];
  for (let i = start; i < end; i++) {
    const t = lapTime ? lapTime[i] : NaN;
    const d = lapDist ? lapDist[i] : NaN;
    if (Number.isFinite(t) && Number.isFinite(d) && t < 0.5 && d > halfTrack) continue;
    keep.push(i);
  }
  return keep;
}

// Linearly interpolate across plateaus of identical lap_time_s. LMU's
// `mCurrentET` updates at scoring rate (~5 Hz, 200 ms quantum), so a 50 Hz
// recording holds the same `lap_time_s` value for ~10 consecutive frames
// before stepping up by 0.2 s. Resampling that staircase onto 1 m bins and
// subtracting two such staircases produces a ±200 ms saw-tooth in Δt every
// time one lap's clock ticks before the other's. This bridges each plateau
// by distributing the next tick's increment uniformly across the held
// frames, using frame index as the 50 Hz wall-clock proxy.
export function smoothLapTime(lapTime, indices) {
  const n = indices.length;
  const out = new Float64Array(n);
  for (let i = 0; i < n; i++) out[i] = lapTime[indices[i]];
  let i = 0;
  while (i < n) {
    let j = i + 1;
    while (j < n && out[j] === out[i]) j++;
    if (j === n) break;  // trailing plateau — leave flat (sub-200 ms tail)
    const v0 = out[i], v1 = out[j], span = j - i;
    for (let k = 1; k < span; k++) out[i + k] = v0 + (v1 - v0) * k / span;
    i = j;
  }
  return out;
}

// Spatial moving average for the Δt array. Even after smoothLapTime, two
// laps' clock ticks land at slightly different distances (1-2 frames of
// recorder phase), so each tick boundary introduces up to ~20 ms of
// plateau-alignment jitter into Δt. The jitter has spatial period equal
// to the plateau length (~7 m at racing speed), so a 41-bin boxcar
// (±20 m) attenuates it by ~6× while preserving features at the scale
// of corners (typically 50-100 m). The kernel is SYMMETRIC and shrinks
// toward the array boundaries (radius = min(maxRadius, i, n-1-i)) so
// the endpoint values are preserved exactly — at the lap-end bin
// (overlapEnd), the smoothed Δt equals the raw (sLapTime - rLapTime)
// at that bin, which equals max(lap_time_s) delta. This is the value
// the "end" text and tooltip read, and it must match the user's
// expectation of "the real lap-time delta."
export function smoothDt(dt, maxRadius = 20) {
  const n = dt.length;
  const out = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const r = Math.min(maxRadius, i, n - 1 - i);
    let sum = 0, cnt = 0;
    for (let k = i - r; k <= i + r; k++) {
      if (isFinite(dt[k])) { sum += dt[k]; cnt++; }
    }
    out[i] = cnt > 0 ? sum / cnt : dt[i];
  }
  return out;
}

// Bridge brief neutral (gear == 0) runs with the previous engaged gear.
// Every shift passes through neutral for 1-3 frames as the clutch
// disengages; rendering those as dips to zero turns a clean gear ladder
// into a comb of teeth at every shift. Threshold of 5 frames (~100 ms at
// 50 Hz) keeps genuine neutral periods (pit-out, coasting) intact.
export function smoothGear(gear, indices, maxNeutralRun = 5) {
  const n = indices.length;
  const out = new Float64Array(n);
  for (let i = 0; i < n; i++) out[i] = gear[indices[i]];
  let i = 0;
  while (i < n) {
    if (out[i] !== 0) { i++; continue; }
    let j = i;
    while (j < n && out[j] === 0) j++;
    if (j - i <= maxNeutralRun && i > 0 && j < n) {
      const prevG = out[i - 1];
      for (let k = i; k < j; k++) out[k] = prevG;
    }
    i = j;
  }
  return out;
}

// ── Sector distance finder ────────────────────────────────────────────────────

export function deriveSectorDistances(entry, segIdx) {
  const segs = entry.segments;
  const seg  = segs[segIdx];
  if (!entry.data.last_sector_1_s || !entry.data.last_sector_2_s) return null;
  if (segIdx >= segs.length - 1) return null; // no next segment

  const nextSeg = segs[segIdx + 1];
  const s1col  = entry.data.last_sector_1_s;
  const s2col  = entry.data.last_sector_2_s;

  // Walk up to 25 frames into next segment for settled sector values (O1/O2)
  const walkEnd = Math.min(nextSeg.start + 25, nextSeg.end);
  let s1 = NaN, cumS2 = NaN;
  for (let fi = nextSeg.start; fi < walkEnd; fi++) {
    const _s1 = s1col[fi], _cs2 = s2col[fi];
    if (!isNaN(_s1) && !isNaN(_cs2) && _s1 > 0 && _cs2 > _s1) {
      s1 = _s1; cumS2 = _cs2;
      break;
    }
  }
  if (isNaN(s1)) return null;

  // Convert split times to distances using lap_time_s within this segment
  const lapT   = entry.data.lap_time_s;
  const lapD   = entry.data.lap_distance_m;
  let d1 = null, d2 = null;
  let prev = seg.start;
  for (let fi = seg.start; fi < seg.end; fi++) {
    if (d1 === null && lapT[fi] >= s1) {
      // Interpolate
      const t0 = lapT[prev], t1 = lapT[fi];
      const d0 = lapD[prev], d1v = lapD[fi];
      const frac = (t0 === t1) ? 0 : (s1 - t0) / (t1 - t0);
      d1 = d0 + frac * (d1v - d0);
    }
    if (d2 === null && lapT[fi] >= cumS2) {
      const t0 = lapT[prev], t1 = lapT[fi];
      const d0 = lapD[prev], d1v = lapD[fi];
      const frac = (t0 === t1) ? 0 : (cumS2 - t0) / (t1 - t0);
      d2 = d0 + frac * (d1v - d0);
      break;
    }
    prev = fi;
  }
  return (d1 !== null || d2 !== null) ? { s1dist: d1, s2dist: d2 } : null;
}

// ── Geometry helpers ──────────────────────────────────────────────────────────

export function niceRange(arr, yFixed, margin = 0.05) {
  if (yFixed) return yFixed;
  let mn = Infinity, mx = -Infinity;
  for (const x of arr) { if (isFinite(x)) { if (x < mn) mn = x; if (x > mx) mx = x; } }
  if (!isFinite(mn)) return [0, 1];
  const span = mx - mn || 1;
  return [mn - span * margin, mx + span * margin];
}

export function buildPolylinePts(xs, ys, toX, toY, step = false) {
  const pts = [];
  for (let i = 0; i < xs.length; i++) {
    if (step && i > 0) {
      // Step plot: draw horizontal segment at previous value before stepping down
      pts.push(`${toX(xs[i]).toFixed(1)},${toY(ys[i - 1]).toFixed(1)}`);
    }
    pts.push(`${toX(xs[i]).toFixed(1)},${toY(ys[i]).toFixed(1)}`);
  }
  return pts.join(' ');
}

export function computeTrackBounds(trackX, trackZ) {
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  for (let i = 0; i < trackX.length; i++) {
    const x = trackX[i], z = trackZ[i];
    if (isFinite(x) && isFinite(z)) {
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
    }
  }
  return { minX, maxX, minZ, maxZ };
}

export function buildTrackTransform(bounds) {
  const width = bounds.maxX - bounds.minX || 1;
  const height = bounds.maxZ - bounds.minZ || 1;
  const scale = Math.min((250 - 2 * 20) / width, (250 - 2 * 20) / height);
  const offsetX = 20 + (250 - 2 * 20 - width * scale) / 2;
  const offsetZ = 20 + (250 - 2 * 20 - height * scale) / 2;
  return {
    toMapX: (x) => offsetX + (x - bounds.minX) * scale,
    // Invert Z-axis: world Z increases in one direction, SVG Y increases downward
    toMapZ: (z) => offsetZ + (bounds.maxZ - z) * scale,
    bounds, scale, offsetX, offsetZ,
  };
}

export function buildTrackPolylinePts(trackX, trackZ, toMapX, toMapZ) {
  const pts = [];
  for (let i = 0; i < trackX.length; i++) {
    if (isFinite(trackX[i]) && isFinite(trackZ[i])) {
      pts.push(`${toMapX(trackX[i]).toFixed(1)},${toMapZ(trackZ[i]).toFixed(1)}`);
    }
  }
  return pts.join(' ');
}

// ── Diagnostics ───────────────────────────────────────────────────────────────

export function computeMedianFrameDistanceDelta(distances) {
  if (distances.length < 2) return 0;
  const deltas = [];
  for (let i = 1; i < distances.length; i++) {
    const d = distances[i] - distances[i - 1];
    if (d > 0) deltas.push(d);
  }
  if (!deltas.length) return 0;
  deltas.sort((a, b) => a - b);
  return deltas[Math.floor(deltas.length / 2)];
}

// ── Nice Y-tick helper (F10) ─────────────────────────────────────────────────
// Primary: smallest step from niceSteps giving 3–5 ticks with ≥30 px gap.
// Fallback: magnitude-rounded step targeting ~4 ticks (handles ranges outside
// the niceSteps domain — very small Δt when comparing same lap, or large slip
// angles from extreme data).
export function computeNiceYTicks(yMin, yMax, plotH, niceSteps) {
  const range = yMax - yMin;
  if (!isFinite(range) || range <= 0) return [yMin, yMax].filter(isFinite);
  for (const step of niceSteps) {
    const startTick = Math.ceil(yMin / step - 1e-9) * step;
    const ticks = [];
    for (let y = startTick; y <= yMax + step * 1e-9; y += step) {
      ticks.push(Math.round(y / step) * step);
    }
    if (ticks.length < 3 || ticks.length > 5) continue;
    if (plotH / Math.max(ticks.length - 1, 1) >= 30) return ticks;
  }
  // Fallback: derive a nice step from magnitude of range/4
  const rawStep = range / 4;
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const norm = rawStep / mag;
  let niceNorm = 10;
  for (const n of [1, 2, 2.5, 5, 10]) { if (n >= norm) { niceNorm = n; break; } }
  const fbStep = niceNorm * mag;
  const fbStart = Math.ceil(yMin / fbStep - 1e-9) * fbStep;
  const fbTicks = [];
  for (let y = fbStart; y <= yMax + fbStep * 1e-9 && fbTicks.length < 7; y += fbStep) {
    fbTicks.push(Math.round(y / fbStep) * fbStep);
  }
  return fbTicks.length >= 2 ? fbTicks : [yMin, (yMin + yMax) / 2, yMax];
}
