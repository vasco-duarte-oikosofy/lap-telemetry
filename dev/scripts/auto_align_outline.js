#!/usr/bin/env node
'use strict';

/**
 * Automated initial alignment of TUMFTM track data to simulator trajectory.
 *
 * Uses iterative closest point (ICP) with a 2D similarity transform
 * (scale, rotation, translation, optional flip) to find a coarse alignment.
 *
 * This is meant as a starting point — the result should be visually verified
 * and refined using the manual_outline_align.html tool.
 *
 * Usage:
 *   node scripts/auto_align_outline.js \
 *     --tumftm-json <track.json> \
 *     --trajectory-json <trajectory.json> \
 *     [--flip-x] [--flip-y] [--reverse] \
 *     [--out <aligned.json>]
 */

const fs = require('fs/promises');
const path = require('path');

// ─── Geometry helpers ────────────────────────────────────────────────────

function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function centroid(pts) {
  let sx = 0, sy = 0;
  for (const p of pts) { sx += p.x; sy += p.y; }
  return { x: sx / pts.length, y: sy / pts.length };
}

function subtract(a, b) { return { x: a.x - b.x, y: a.y - b.y }; }
function add(a, b) { return { x: a.x + b.x, y: a.y + b.y }; }
function scale2(a, s) { return { x: a.x * s, y: a.y * s }; }

function transformPoint(p, params) {
  let x = p.x * (params.flip_x ? -1 : 1);
  let y = p.y * (params.flip_y ? -1 : 1);
  const c = Math.cos(params.rotation_rad);
  const s = Math.sin(params.rotation_rad);
  return {
    x: params.scale * (x * c - y * s) + params.translate_x,
    y: params.scale * (x * s + y * c) + params.translate_y
  };
}

// ─── Resample a polyline to n evenly-spaced points ────────────────────────

function resamplePolyline(pts, n) {
  if (pts.length < 2) return pts;
  // compute cumulative arc length
  const cumLen = [0];
  for (let i = 1; i < pts.length; i++) {
    cumLen.push(cumLen[i - 1] + dist(pts[i - 1], pts[i]));
  }
  const totalLen = cumLen[cumLen.length - 1];
  if (totalLen === 0) return [pts[0]];

  const result = [];
  for (let i = 0; i < n; i++) {
    const targetLen = (i / (n - 1)) * totalLen;
    // find segment
    let seg = 1;
    while (seg < cumLen.length - 1 && cumLen[seg] < targetLen) seg++;
    const segLen = cumLen[seg] - cumLen[seg - 1];
    const t = segLen > 0 ? (targetLen - cumLen[seg - 1]) / segLen : 0;
    result.push({
      x: pts[seg - 1].x + t * (pts[seg].x - pts[seg - 1].x),
      y: pts[seg - 1].y + t * (pts[seg].y - pts[seg - 1].y)
    });
  }
  return result;
}

// ─── Nearest neighbor search (brute force, fine for ~1000 pts) ────────────

function nearestNeighbor(pt, targets) {
  let bestDist = Infinity, bestIdx = 0;
  for (let i = 0; i < targets.length; i++) {
    const d = dist(pt, targets[i]);
    if (d < bestDist) { bestDist = d; bestIdx = i; }
  }
  return { idx: bestIdx, dist: bestDist };
}

// ─── ICP with similarity transform ────────────────────────────────────────

/**
 * Estimate optimal similarity transform from pairs of corresponding points.
 * Procrustes analysis: finds scale, rotation, translation that minimizes
 * sum of squared distances between source and target.
 */
function procrustes(sourcePts, targetPts) {
  const srcC = centroid(sourcePts);
  const tgtC = centroid(targetPts);

  // Center both
  const srcCentered = sourcePts.map(p => subtract(p, srcC));
  const tgtCentered = targetPts.map(p => subtract(p, tgtC));

  // Compute scale
  let srcScale = 0, tgtScale = 0;
  for (const p of srcCentered) srcScale += p.x * p.x + p.y * p.y;
  for (const p of tgtCentered) tgtScale += p.x * p.x + p.y * p.y;
  srcScale = Math.sqrt(srcScale / srcCentered.length);
  tgtScale = Math.sqrt(tgtScale / tgtCentered.length);
  const scaleEstimate = srcScale > 0 ? tgtScale / srcScale : 1;

  // Normalize
  const srcNorm = srcCentered.map(p => scale2(p, 1 / (srcScale || 1)));
  const tgtNorm = tgtCentered.map(p => scale2(p, 1 / (tgtScale || 1)));

  // Rotation via cross/correlation
  let num = 0, den = 0;
  for (let i = 0; i < srcNorm.length; i++) {
    num += srcNorm[i].x * tgtNorm[i].y - srcNorm[i].y * tgtNorm[i].x;
    den += srcNorm[i].x * tgtNorm[i].x + srcNorm[i].y * tgtNorm[i].y;
  }
  const rotation_rad = Math.atan2(num, den);

  // Translation
  const translate_x = tgtC.x - scaleEstimate * (srcC.x * Math.cos(rotation_rad) - srcC.y * Math.sin(rotation_rad));
  const translate_y = tgtC.y - scaleEstimate * (srcC.x * Math.sin(rotation_rad) + srcC.y * Math.cos(rotation_rad));

  return { scale: scaleEstimate, rotation_rad, translate_x, translate_y };
}

/**
 * Run ICP iterations to align source to target.
 * source: array of {x, y} in TUMFTM coordinates
 * target: array of {x, y} in sim coordinates
 * opts: { flip_x, flip_y, iterations, resampleN }
 */
function runICP(source, target, opts = {}) {
  const iterations = opts.iterations || 50;
  const resampleN = opts.resampleN || Math.min(source.length, target.length, 500);
  const flipX = opts.flip_x || false;
  const flipY = opts.flip_y || false;

  // Resample both to same point count
  const srcResampled = resamplePolyline(source, resampleN);
  const tgtResampled = resamplePolyline(target, resampleN);

  // Pre-flip
  const srcFlipped = srcResampled.map(p => ({
    x: p.x * (flipX ? -1 : 1),
    y: p.y * (flipY ? -1 : 1)
  }));

  let params = { scale: 1, rotation_rad: 0, translate_x: 0, translate_y: 0 };
  let prevError = Infinity;

  for (let iter = 0; iter < iterations; iter++) {
    // Transform source with current params
    const transformed = srcFlipped.map(p => transformPoint(p, params));

    // Build correspondences (nearest neighbor)
    const pairs = [];
    for (let i = 0; i < transformed.length; i++) {
      const { idx } = nearestNeighbor(transformed[i], tgtResampled);
      pairs.push({ src: srcFlipped[i], tgt: tgtResampled[idx] });
    }

    // Also add reverse correspondences for better coverage
    for (let i = 0; i < tgtResampled.length; i++) {
      const { idx } = nearestNeighbor(tgtResampled[i], transformed);
      pairs.push({ src: srcFlipped[idx], tgt: tgtResampled[i] });
    }

    // Estimate transform from correspondences
    const srcPts = pairs.map(p => p.src);
    const tgtPts = pairs.map(p => p.tgt);
    const newParams = procrustes(srcPts, tgtPts);

    params = {
      scale: newParams.scale,
      rotation_rad: newParams.rotation_rad,
      translate_x: newParams.translate_x,
      translate_y: newParams.translate_y
    };

    // Compute error
    const retransformed = srcFlipped.map(p => transformPoint(p, params));
    let totalError = 0;
    for (const p of retransformed) {
      totalError += nearestNeighbor(p, tgtResampled).dist;
    }
    const meanError = totalError / retransformed.length;

    if (Math.abs(prevError - meanError) < 0.01) break;
    prevError = meanError;
  }

  return { ...params, flip_x: flipX, flip_y: flipY };
}

// ─── Boundary computation ────────────────────────────────────────────────

function computeBoundaries(centerline) {
  const left = [], right = [];
  const n = centerline.length;
  for (let i = 0; i < n; i++) {
    const prev = centerline[(i - 1 + n) % n];
    const next = centerline[(i + 1) % n];
    const dx = next.x - prev.x, dy = next.y - prev.y;
    const len = Math.hypot(dx, dy) || 1;
    const nx = dy / len, ny = -dx / len;
    const wr = Number.isFinite(centerline[i].w_right) ? centerline[i].w_right : 0;
    const wl = Number.isFinite(centerline[i].w_left) ? centerline[i].w_left : 0;
    right.push({ x: centerline[i].x + nx * wr, y: centerline[i].y + ny * wr });
    left.push({ x: centerline[i].x - nx * wl, y: centerline[i].y - ny * wl });
  }
  return { left, right };
}

// ─── Outline JSON generation ─────────────────────────────────────────────

function generateOutline(tumftmTrack, params, simTrackName, alignmentNotes) {
  // Apply flip to source points
  const centerSource = tumftmTrack.points.map(p => ({
    x: p.x * (params.flip_x ? -1 : 1),
    y: p.y * (params.flip_y ? -1 : 1),
    w_right: p.w_right,
    w_left: p.w_left
  }));

  // Compute boundaries in source space
  const bounds = computeBoundaries(centerSource);

  // Transform all geometry
  const safeParams = {
    scale: params.scale,
    rotation_rad: params.rotation_rad,
    translate_x: params.translate_x,
    translate_y: params.translate_y,
    flip_x: false, // already applied
    flip_y: false   // already applied
  };

  const centerline = centerSource.map(p => transformPoint(p, safeParams));
  const left_boundary = bounds.left.map(p => transformPoint(p, safeParams));
  const right_boundary = bounds.right.map(p => transformPoint(p, safeParams));

  return {
    schema_version: 1,
    source: 'TUMFTM manual alignment',
    track_name: tumftmTrack.track_name || 'Unknown',
    sim_track_name: simTrackName,
    layout_name: 'default',
    coordinate_system: 'sim_xy',
    units: 'sim_units',
    track_name_mapping: {
      canonical_sim_track_name: simTrackName.toLowerCase().replace(/\s+/g, '-'),
      canonical_lmu_track_name: tumftmTrack.track_name,
      accepted_sim_track_names: [simTrackName.toLowerCase().replace(/\s+/g, '-')],
      accepted_lmu_track_names: [tumftmTrack.track_name],
      notes: 'Auto-generated initial mapping; refine as needed.'
    },
    alignment: {
      method: 'manual_similarity_transform',
      ...params,
      notes: alignmentNotes
    },
    visual_qa: {
      status: 'pending',
      notes: 'Auto-aligned; needs visual verification using tools/manual_outline_align.html'
    },
    caveats: [
      'TUMFTM widths are satellite/image-derived approximations, not official FIA geometry.',
      'This outline is visual context only and is not authoritative simulator track-limits data.'
    ],
    centerline,
    left_boundary,
    right_boundary
  };
}

// ─── Main ─────────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const opts = { flip_x: false, flip_y: false, reverse: false, iterations: 50 };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--tumftm-json') opts.tumftmJson = argv[++i];
    else if (arg === '--trajectory-json') opts.trajectoryJson = argv[++i];
    else if (arg === '--sim-track-name') opts.simTrackName = argv[++i];
    else if (arg === '--flip-x') opts.flip_x = true;
    else if (arg === '--flip-y') opts.flip_y = true;
    else if (arg === '--reverse') opts.reverse = true;
    else if (arg === '--iterations') opts.iterations = Number(argv[++i]);
    else if (arg === '--out') opts.outPath = argv[++i];
    else if (arg === '--try-all-flips') opts.tryAllFlips = true;
    else if (!arg.startsWith('--')) { if (!opts.tumftmJson) opts.tumftmJson = arg; else if (!opts.trajectoryJson) opts.trajectoryJson = arg; }
    else throw new Error(`unknown argument: ${arg}`);
  }
  return opts;
}

async function main(argv) {
  const opts = parseArgs(argv);
  if (!opts.tumftmJson || !opts.trajectoryJson) {
    throw new Error('usage: auto_align_outline.js --tumftm-json <track.json> --trajectory-json <traj.json> [--flip-x] [--flip-y] [--try-all-flips] [--out <out.json>]');
  }

  const tumftmTrack = JSON.parse(await fs.readFile(opts.tumftmJson, 'utf8'));
  const trajectory = JSON.parse(await fs.readFile(opts.trajectoryJson, 'utf8'));

  // Get sim reference points
  const simPoints = [];
  if (Array.isArray(trajectory.trajectories)) {
    for (const t of trajectory.trajectories) {
      for (const p of (t.points || [])) {
        const x = p.x ?? p.sim_x, y = p.y ?? p.sim_y;
        if (Number.isFinite(x) && Number.isFinite(y)) simPoints.push({ x, y });
      }
    }
  } else if (Array.isArray(trajectory.points)) {
    for (const p of trajectory.points) {
      const x = p.x ?? p.sim_x, y = p.y ?? p.sim_y;
      if (Number.isFinite(x) && Number.isFinite(y)) simPoints.push({ x, y });
    }
  }

  if (simPoints.length < 10) throw new Error(`too few sim points: ${simPoints.length}`);
  if (!tumftmTrack.points || tumftmTrack.points.length < 10) throw new Error(`too few TUMFTM points`);

  const source = tumftmTrack.points.map(p => ({ x: p.x, y: p.y, w_right: p.w_right, w_left: p.w_left }));
  const target = simPoints;

  if (opts.tryAllFlips) {
    // Try all 4 flip combinations and pick the best
    const flipConfigs = [
      { flip_x: false, flip_y: false, label: 'none' },
      { flip_x: true,  flip_y: false, label: 'flip_x' },
      { flip_x: false, flip_y: true,  label: 'flip_y' },
      { flip_x: true,  flip_y: true,  label: 'both' }
    ];

    let bestResult = null, bestError = Infinity, bestLabel = '';
    for (const fc of flipConfigs) {
      const result = runICP(source, target, { ...opts, ...fc });
      // Compute final error
      const flipped = source.map(p => ({
        x: p.x * (fc.flip_x ? -1 : 1),
        y: p.y * (fc.flip_y ? -1 : 1)
      }));
      const transformed = flipped.map(p => transformPoint(p, result));
      const resampledTarget = resamplePolyline(target, Math.min(target.length, 500));
      let totalError = 0;
      for (const p of transformed) totalError += nearestNeighbor(p, resampledTarget).dist;
      const meanError = totalError / transformed.length;
      console.log(`  flip=${fc.label}: scale=${result.scale.toFixed(4)} rot=${(result.rotation_rad*180/Math.PI).toFixed(2)}° tx=${result.translate_x.toFixed(1)} ty=${result.translate_y.toFixed(1)} meanError=${meanError.toFixed(2)}`);
      if (meanError < bestError) {
        bestError = meanError;
        bestResult = result;
        bestLabel = fc.label;
      }
    }
    console.log(`\nBest: flip=${bestLabel} meanError=${bestError.toFixed(2)}`);
    Object.assign(opts, bestResult);
  } else {
    const result = runICP(source, target, opts);
    Object.assign(opts, result);
  }

  const simTrackName = opts.simTrackName || trajectory.track_name || 'Unknown';
  const outline = generateOutline(tumftmTrack, opts, simTrackName, `Auto-aligned via ICP. ${opts.tryAllFlips ? 'Tried all flip combinations.' : `Used flip_x=${opts.flip_x}, flip_y=${opts.flip_y}.`} Visual verification needed.`);

  const outPath = opts.outPath || `data/track-outlines/${simTrackName.toLowerCase().replace(/\s+/g, '-')}.json`;
  await fs.mkdir(path.dirname(outPath), { recursive: true });
  await fs.writeFile(outPath, JSON.stringify(outline, null, 2) + '\n');
  console.log(`\nWrote ${outPath}`);
  console.log(`Alignment parameters:`, JSON.stringify({
    scale: opts.scale?.toFixed?.(4) ?? outline.alignment.scale,
    rotation_rad: opts.rotation_rad?.toFixed?.(4) ?? outline.alignment.rotation_rad,
    translate_x: Math.round(opts.translate_x ?? outline.alignment.translate_x),
    translate_y: Math.round(opts.translate_y ?? outline.alignment.translate_y),
    flip_x: opts.flip_x,
    flip_y: opts.flip_y
  }, null, 2));
}

module.exports = { runICP, procrustes, computeBoundaries, generateOutline, transformPoint, resamplePolyline, nearestNeighbor };

if (require.main === module) {
  main(process.argv.slice(2)).catch(err => {
    console.error(`auto_align_outline failed: ${err.message}`);
    process.exit(1);
  });
}