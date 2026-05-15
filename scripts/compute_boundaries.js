#!/usr/bin/env node
/**
 * Boundary polyline derivation — computes left/right boundary polylines
 * from a center/path polyline and a width profile.
 *
 * Usage:
 *   node scripts/compute_boundaries.js --path <path.json> --profile <profile.json> \
 *     --out <boundaries.json> [--smooth] [--smooth-boundary <window>] [--overwrite]
 *
 * Options:
 *   --smooth              Use smoothed widths (left_width_smooth_m / right_width_smooth_m)
 *   --smooth-boundary N   Smooth boundary polyline positions with local polynomial window N
 *   --overwrite          Replace existing output file (default: refuse)
 */

'use strict';

const fs = require('fs/promises');
const path = require('path');

/**
 * Compute tangent and normal at a point in a polyline.
 *
 * Interior points: tangent = normalized(previous → next).
 * Endpoints: tangent = normalized(point → neighbor).
 * Normal: rotate tangent -90° in x-z plane: (-tz, tx).
 *   This gives "left" normal when traveling forward (+z).
 *
 * Returns { tx, tz, nx, nz } or { tx:0, tz:0, nx:0, nz:0 } for
 * degenerate cases (single point or coincident neighbors).
 */
function computeTangentNormal(points, index) {
  if (points.length < 2) {
    return { tx: 0, tz: 0, nx: 0, nz: 0 };
  }

  let dx, dz;
  if (index === 0) {
    dx = points[1].x_m - points[0].x_m;
    dz = points[1].z_m - points[0].z_m;
  } else if (index === points.length - 1) {
    dx = points[index].x_m - points[index - 1].x_m;
    dz = points[index].z_m - points[index - 1].z_m;
  } else {
    dx = points[index + 1].x_m - points[index - 1].x_m;
    dz = points[index + 1].z_m - points[index - 1].z_m;
  }

  const len = Math.sqrt(dx * dx + dz * dz);
  if (len < 1e-12) {
    return { tx: 0, tz: 0, nx: 0, nz: 0 };
  }

  const tx = dx / len;
  const tz = dz / len;
  // Left normal: rotate tangent -90° → (-tz, tx)
  const nx = -tz;
  const nz = tx;
  return { tx, tz, nx, nz };
}

/**
 * Fit a local polynomial around one point and return the value at t=0.
 * A quadratic fit preserves straight lines exactly while avoiding the curve
 * shrinkage of a raw moving average. Falls back to linear/identity for small
 * segments.
 */
function localPolynomialValue(points, index, start, end, window, field) {
  const rows = [];
  const centerS = points[index].s_m;
  for (let w = -window; w <= window; w++) {
    const ni = index + w;
    if (ni < start || ni >= end) continue;
    rows.push({ t: points[ni].s_m - centerS, y: points[ni][field] });
  }

  if (rows.length < 3) {
    return points[index][field];
  }

  let n = 0, st = 0, st2 = 0, st3 = 0, st4 = 0;
  let sy = 0, sty = 0, st2y = 0;
  for (const r of rows) {
    const t2 = r.t * r.t;
    n++;
    st += r.t;
    st2 += t2;
    st3 += t2 * r.t;
    st4 += t2 * t2;
    sy += r.y;
    sty += r.t * r.y;
    st2y += t2 * r.y;
  }

  const det = n * (st2 * st4 - st3 * st3)
    - st * (st * st4 - st2 * st3)
    + st2 * (st * st3 - st2 * st2);

  if (Math.abs(det) < 1e-9) {
    return points[index][field];
  }

  // Cramer's rule for coefficient a in y = a + bt + ct².
  const detA = sy * (st2 * st4 - st3 * st3)
    - st * (sty * st4 - st3 * st2y)
    + st2 * (sty * st3 - st2 * st2y);
  return detA / det;
}

/**
 * Smooth boundary polyline positions with local polynomial smoothing.
 *
 * @param {Array} boundaryPoints - [{ s_m, x_m, z_m, width_m, status, confidence }, ...]
 * @param {number} window - Half-window size (±window bins). 0 or 1 = no smoothing.
 * @param {number} [binSize] - Bin size in meters for gap detection. Default 1.
 *   Gaps where s_m jumps > binSize*2 are segment breaks (not bridged).
 * @returns {Array} Smoothed boundary points (same length, x_m and z_m smoothed).
 */
function smoothBoundary(boundaryPoints, window, binSize = 1) {
  if (window <= 1 || boundaryPoints.length === 0) {
    return boundaryPoints.map(p => ({ ...p }));
  }

  const result = boundaryPoints.map(p => ({ ...p }));
  const maxGap = binSize * 2;
  const isBarrier = boundaryPoints.map(p => p.width_m === 0);

  let start = null;
  for (let i = 0; i <= boundaryPoints.length; i++) {
    const atEnd = i === boundaryPoints.length;
    const barrier = !atEnd && isBarrier[i];
    const gapBefore = !atEnd && i > 0 && boundaryPoints[i].s_m - boundaryPoints[i - 1].s_m > maxGap;

    if (start != null && (atEnd || barrier || gapBefore)) {
      for (let j = start; j < i; j++) {
        result[j].x_m = localPolynomialValue(boundaryPoints, j, start, i, window, 'x_m');
        result[j].z_m = localPolynomialValue(boundaryPoints, j, start, i, window, 'z_m');
      }
      start = null;
    }

    if (barrier) {
      result[i].x_m = boundaryPoints[i].x_m;
      result[i].z_m = boundaryPoints[i].z_m;
      continue;
    }

    if (!atEnd && start == null) start = i;
  }

  return result;
}

/**
 * Derive left and right boundary polylines from path points + width samples.
 *
 * @param {Array} pathPoints  - [{ s_m, x_m, z_m, sample_count }, ...]
 * @param {Array} profileSamples - [{ s_m, left_width_m, right_width_m, (left_width_smooth_m, right_width_smooth_m), status, confidence }, ...]
 * @param {boolean} useSmooth - Use smoothed widths instead of raw
 * @param {number} [smoothBoundaryWindow] - Window for boundary smoothing (0 = no smoothing)
 * @returns {{ left, right, use_smooth, smooth_boundary_window, summary }}
 */
function computeBoundaries({ pathPoints, profileSamples, useSmooth, smoothBoundaryWindow = 0 }) {
  // Build profile lookup by s_m
  const profileByS = new Map();
  for (const s of profileSamples) {
    profileByS.set(s.s_m, s);
  }

  let left = [];
  let right = [];
  let unmatchedPath = 0;

  for (let i = 0; i < pathPoints.length; i++) {
    const pp = pathPoints[i];
    const ws = profileByS.get(pp.s_m);
    if (!ws) {
      unmatchedPath++;
      continue;
    }

    const leftWidth = useSmooth ? (ws.left_width_smooth_m ?? ws.left_width_m) : ws.left_width_m;
    const rightWidth = useSmooth ? (ws.right_width_smooth_m ?? ws.right_width_m) : ws.right_width_m;

    // Compute tangent/normal for this path point
    const { nx, nz } = computeTangentNormal(pathPoints, i);

    // Offset: left = path + normal * leftWidth, right = path - normal * rightWidth
    left.push({
      s_m: pp.s_m,
      x_m: pp.x_m + nx * leftWidth,
      z_m: pp.z_m + nz * leftWidth,
      width_m: leftWidth,
      status: ws.status,
      confidence: ws.confidence,
    });

    right.push({
      s_m: pp.s_m,
      x_m: pp.x_m - nx * rightWidth,
      z_m: pp.z_m - nz * rightWidth,
      width_m: rightWidth,
      status: ws.status,
      confidence: ws.confidence,
    });
  }

  // Apply boundary smoothing if requested
  if (smoothBoundaryWindow > 0) {
    // Determine bin_size_m from the path data
    const binSize = pathPoints.length > 1
      ? pathPoints[1].s_m - pathPoints[0].s_m
      : 1;
    left = smoothBoundary(left, smoothBoundaryWindow, binSize);
    right = smoothBoundary(right, smoothBoundaryWindow, binSize);
  }

  return {
    left,
    right,
    use_smooth: useSmooth,
    smooth_boundary_window: smoothBoundaryWindow || 0,
    summary: {
      path_points: pathPoints.length,
      profile_samples: profileSamples.length,
      matched_bins: left.length,
      unmatched_path: unmatchedPath,
      left_boundary_points: left.length,
      right_boundary_points: right.length,
    },
  };
}

async function computeBoundariesFromFiles({ pathPath, profilePath, outPath, useSmooth, smoothBoundaryWindow = 0, overwrite }) {
  const pathData = JSON.parse(await fs.readFile(pathPath, 'utf8'));
  const profileData = JSON.parse(await fs.readFile(profilePath, 'utf8'));

  if (pathData.bin_size_m !== profileData.bin_size_m) {
    throw new Error(`bin_size_m mismatch: path=${pathData.bin_size_m} profile=${profileData.bin_size_m}`);
  }

  const result = computeBoundaries({
    pathPoints: pathData.points,
    profileSamples: profileData.samples,
    useSmooth,
    smoothBoundaryWindow,
  });

  const output = {
    track_id: pathData.track_id,
    layout_id: pathData.layout_id,
    bin_size_m: pathData.bin_size_m,
    use_smooth: useSmooth,
    smooth_boundary_window: result.smooth_boundary_window,
    left: result.left,
    right: result.right,
    summary: result.summary,
  };

  await fs.mkdir(path.dirname(outPath), { recursive: true });
  try {
    await fs.writeFile(outPath, `${JSON.stringify(output, null, 2)}\n`, { flag: overwrite ? 'w' : 'wx' });
  } catch (err) {
    if (err && err.code === 'EEXIST') {
      throw new Error(`output exists: ${outPath} (pass --overwrite to replace)`);
    }
    throw err;
  }

  return output;
}

function parseArgs(argv) {
  const opts = { overwrite: false, smooth: false, smoothBoundary: 0 };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--overwrite') {
      opts.overwrite = true;
    } else if (arg === '--smooth') {
      opts.smooth = true;
    } else if (arg === '--smooth-boundary') {
      const value = argv[++i];
      if (!value) throw new Error('missing value for --smooth-boundary');
      if (!/^\d+$/.test(value)) {
        throw new Error('--smooth-boundary must be a non-negative integer');
      }
      opts.smoothBoundary = parseInt(value, 10);
    } else if (arg === '--path' || arg === '--profile' || arg === '--out') {
      const value = argv[++i];
      if (!value) throw new Error(`missing value for ${arg}`);
      const key = arg.slice(2);
      opts[key] = value;
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }
  if (!opts.path) throw new Error('missing --path');
  if (!opts.profile) throw new Error('missing --profile');
  if (!opts.out) throw new Error('missing --out');
  return opts;
}

async function main(argv) {
  const opts = parseArgs(argv);
  const result = await computeBoundariesFromFiles({
    pathPath: opts.path,
    profilePath: opts.profile,
    outPath: opts.out,
    useSmooth: opts.smooth,
    smoothBoundaryWindow: opts.smoothBoundary,
    overwrite: opts.overwrite,
  });
  const s = result.summary;
  console.log(`wrote ${opts.out} (${s.left_boundary_points} left, ${s.right_boundary_points} right, ${s.unmatched_path} unmatched)`);
}

module.exports = { computeBoundaries, computeBoundariesFromFiles, computeTangentNormal, smoothBoundary };

if (require.main === module) {
  main(process.argv.slice(2)).catch(err => {
    console.error(`boundary computation failed: ${err.message}`);
    process.exit(1);
  });
}