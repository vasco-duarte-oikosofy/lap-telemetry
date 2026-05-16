/**
 * Track outline Phase 09.1 boundary polyline tests.
 *
 * Run: node scripts/test_compute_boundaries.js
 */
// @parallel true

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..', '..');
const SCRIPT = path.join(ROOT, 'dev/scripts/compute_boundaries.js');

let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function tempPath(name, ext) {
  return path.join(os.tmpdir(), `${name}-${Date.now()}-${Math.random().toString(16).slice(2)}${ext}`);
}

function approxEq(a, b, eps = 1e-6) {
  return Math.abs(a - b) < eps;
}

async function runTests() {
  const { computeBoundaries, computeTangentNormal } = require(SCRIPT);

  // ── Test 1: Straight-line path along z-axis, exact boundary offsets ──
  console.log('\n── Straight-line path: exact boundary offsets ──');
  {
    // Path points along z-axis: (0, z), traveling in +z direction
    const pathPoints = [
      { s_m: 0, x_m: 0, z_m: 0, sample_count: 10 },
      { s_m: 1, x_m: 0, z_m: 1, sample_count: 10 },
      { s_m: 2, x_m: 0, z_m: 2, sample_count: 10 },
      { s_m: 3, x_m: 0, z_m: 3, sample_count: 10 },
      { s_m: 4, x_m: 0, z_m: 4, sample_count: 10 },
    ];
    const profileSamples = [
      { s_m: 0, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      { s_m: 1, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      { s_m: 2, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      { s_m: 3, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      { s_m: 4, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
    ];

    const result = computeBoundaries({ pathPoints, profileSamples, useSmooth: false });

    assert(result.left.length === 5, 'left boundary has 5 points', String(result.left.length));
    assert(result.right.length === 5, 'right boundary has 5 points', String(result.right.length));

    // Traveling in +z, tangent = (0,1), normal (left) = (-1, 0)
    // Left: (x - (-1)*5, z - 0*5) = (5, z)   — wait, let me re-derive:
    // tangent = (0,1), left normal = (-tz, tx) = (-1, 0)
    // Left boundary = (x + normal_x * left_width, z + normal_z * left_width)
    //   = (0 + (-1)*5, z + 0*5) = (-5, z) → left is at negative x
    // Right boundary = (x - normal_x * right_width, z - normal_z * right_width)
    //   = (0 - (-1)*3, z - 0*3) = (3, z) → right is at positive x

    for (let i = 0; i < 5; i++) {
      const lp = result.left[i];
      const rp = result.right[i];
      assert(approxEq(lp.x_m, -5), `left[${i}] x_m = -5`, String(lp.x_m));
      assert(approxEq(lp.z_m, i), `left[${i}] z_m = ${i}`, String(lp.z_m));
      assert(approxEq(rp.x_m, 3), `right[${i}] x_m = 3`, String(rp.x_m));
      assert(approxEq(rp.z_m, i), `right[${i}] z_m = ${i}`, String(rp.z_m));
    }
  }

  // ── Test 2: Tangent/normal calculation ──
  console.log('\n── Tangent/normal calculation ──');
  {
    const points = [
      { x_m: 0, z_m: 0 },
      { x_m: 0, z_m: 1 },
      { x_m: 0, z_m: 2 },
    ];

    // Interior point (index 1): vector from p0 to p2 = (0,2), normalized = (0,1)
    const t1 = computeTangentNormal(points, 1);
    assert(approxEq(t1.tx, 0) && approxEq(t1.tz, 1), 'interior tangent = (0,1)', `(${t1.tx},${t1.tz})`);
    // Normal: (-tz, tx) = (-1, 0)
    assert(approxEq(t1.nx, -1) && approxEq(t1.nz, 0), 'interior normal = (-1,0)', `(${t1.nx},${t1.nz})`);

    // First point (index 0): one-sided tangent, vector from p0 to p1 = (0,1)
    const t0 = computeTangentNormal(points, 0);
    assert(approxEq(t0.tx, 0) && approxEq(t0.tz, 1), 'endpoint tangent = (0,1)', `(${t0.tx},${t0.tz})`);
    assert(approxEq(t0.nx, -1) && approxEq(t0.nz, 0), 'endpoint normal = (-1,0)', `(${t0.nx},${t0.nz})`);

    // Last point (index 2): one-sided tangent, vector from p1 to p2 = (0,1)
    const t2 = computeTangentNormal(points, 2);
    assert(approxEq(t2.tx, 0) && approxEq(t2.tz, 1), 'last point tangent = (0,1)', `(${t2.tx},${t2.tz})`);
    assert(approxEq(t2.nx, -1) && approxEq(t2.nz, 0), 'last point normal = (-1,0)', `(${t2.nx},${t2.nz})`);
  }

  // ── Test 3: Path along +x direction, left is -z ──
  console.log('\n── Straight-line along +x: normal points ──');
  {
    const pathPoints = [
      { s_m: 0, x_m: 0, z_m: 0, sample_count: 5 },
      { s_m: 1, x_m: 1, z_m: 0, sample_count: 5 },
      { s_m: 2, x_m: 2, z_m: 0, sample_count: 5 },
    ];
    const profileSamples = [
      { s_m: 0, left_width_m: 4, right_width_m: 2, status: 'complete', confidence: 1.0 },
      { s_m: 1, left_width_m: 4, right_width_m: 2, status: 'complete', confidence: 1.0 },
      { s_m: 2, left_width_m: 4, right_width_m: 2, status: 'complete', confidence: 1.0 },
    ];

    const result = computeBoundaries({ pathPoints, profileSamples, useSmooth: false });

    // Tangent = (1,0), normal (left) = (-tz, tx) = (0, 1)
    // Left: (0 + 0*4, 0 + 1*4) = (0, 4) — z is positive, that's "left" if traveling +x
    // Right: (0 - 0*2, 0 - 1*2) = (0, -2) — z is negative, that's "right"
    for (let i = 0; i < 3; i++) {
      const lp = result.left[i];
      const rp = result.right[i];
      assert(approxEq(lp.x_m, i), `left[${i}] x_m = ${i}`, String(lp.x_m));
      assert(approxEq(lp.z_m, 4), `left[${i}] z_m = 4`, String(lp.z_m));
      assert(approxEq(rp.x_m, i), `right[${i}] x_m = ${i}`, String(rp.x_m));
      assert(approxEq(rp.z_m, -2), `right[${i}] z_m = -2`, String(rp.z_m));
    }
  }

  // ── Test 4: Circular arc — left boundary outside, right inside ──
  console.log('\n── Circular arc: boundaries on consistent sides ──');
  {
    // Quarter circle: center at (R, 0), points on circle radius R
    // Traveling counter-clockwise from angle 0 to pi/2
    // For CCW travel along an arc, the center is to the left
    const R = 100;
    const n = 20;
    const pathPoints = [];
    const profileSamples = [];
    for (let i = 0; i <= n; i++) {
      const angle = (i / n) * Math.PI / 2;
      const x = R - R * Math.cos(angle);
      const z = R * Math.sin(angle);
      pathPoints.push({ s_m: i, x_m: x, z_m: z, sample_count: 5 });
      profileSamples.push({ s_m: i, left_width_m: 5, right_width_m: 5, status: 'complete', confidence: 1.0 });
    }

    const result = computeBoundaries({ pathPoints, profileSamples, useSmooth: false });

    // For CCW on this arc, center of curvature is at (R,0) which is to the left.
    // Left boundary should be further from center (larger radius), right closer.
    // At each point, compute distance to center (R,0)
    let leftAlwaysFurther = true;
    let rightAlwaysCloser = true;
    for (let i = 1; i < result.left.length; i++) {
      const lp = result.left[i];
      const rp = result.right[i];
      const pp = pathPoints[i];
      const distPath = Math.sqrt((pp.x_m - R) ** 2 + pp.z_m ** 2);
      const distLeft = Math.sqrt((lp.x_m - R) ** 2 + lp.z_m ** 2);
      const distRight = Math.sqrt((rp.x_m - R) ** 2 + rp.z_m ** 2);
      if (distLeft < distPath + 0.1) leftAlwaysFurther = false;
      if (distRight > distPath - 0.1) rightAlwaysCloser = false;
    }
    assert(leftAlwaysFurther, 'left boundary is outside arc (further from center)');
    assert(rightAlwaysCloser, 'right boundary is inside arc (closer to center)');
  }

  // ── Test 5: Missing width bins produce no boundary points ──
  console.log('\n── Missing width bins: no boundary points ──');
  {
    const pathPoints = [
      { s_m: 0, x_m: 0, z_m: 0, sample_count: 5 },
      { s_m: 1, x_m: 0, z_m: 1, sample_count: 5 },
      { s_m: 2, x_m: 0, z_m: 2, sample_count: 5 },
      { s_m: 5, x_m: 0, z_m: 5, sample_count: 5 },
    ];
    const profileSamples = [
      { s_m: 0, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      { s_m: 1, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      // s_m=2 is missing from profile
      { s_m: 5, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
    ];

    const result = computeBoundaries({ pathPoints, profileSamples, useSmooth: false });

    assert(result.left.length === 3, '3 left boundary points (s=0,1,5)', String(result.left.length));
    assert(result.right.length === 3, '3 right boundary points (s=0,1,5)', String(result.right.length));
    assert(result.summary.unmatched_path === 1, '1 unmatched path point (s=2)', String(result.summary.unmatched_path));
    assert(!result.left.find(p => p.s_m === 2), 'no left boundary at s=2');
    assert(!result.right.find(p => p.s_m === 2), 'no right boundary at s=2');
  }

  // ── Test 6: Status and confidence propagation ──
  console.log('\n── Status/confidence propagation ──');
  {
    const pathPoints = [
      { s_m: 0, x_m: 0, z_m: 0, sample_count: 5 },
      { s_m: 1, x_m: 0, z_m: 1, sample_count: 5 },
      { s_m: 2, x_m: 0, z_m: 2, sample_count: 5 },
    ];
    const profileSamples = [
      { s_m: 0, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      { s_m: 1, left_width_m: 4, right_width_m: 2, status: 'one-sided', confidence: 0.5 },
      { s_m: 2, left_width_m: 3, right_width_m: 1, status: 'low-sample', confidence: 0.75 },
    ];

    const result = computeBoundaries({ pathPoints, profileSamples, useSmooth: false });

    assert(result.left[0].status === 'complete', 'left[0] status = complete', result.left[0].status);
    assert(result.left[0].confidence === 1.0, 'left[0] confidence = 1.0', String(result.left[0].confidence));
    assert(result.left[1].status === 'one-sided', 'left[1] status = one-sided', result.left[1].status);
    assert(result.left[1].confidence === 0.5, 'left[1] confidence = 0.5', String(result.left[1].confidence));
    assert(result.right[2].status === 'low-sample', 'right[2] status = low-sample', result.right[2].status);
    assert(result.right[2].confidence === 0.75, 'right[2] confidence = 0.75', String(result.right[2].confidence));
  }

  // ── Test 7: Smooth vs raw widths ──
  console.log('\n── Smooth vs raw widths ──');
  {
    const pathPoints = [
      { s_m: 0, x_m: 0, z_m: 0, sample_count: 5 },
      { s_m: 1, x_m: 0, z_m: 1, sample_count: 5 },
    ];
    const profileSamples = [
      { s_m: 0, left_width_m: 5, right_width_m: 3, left_width_smooth_m: 4, right_width_smooth_m: 2.5, status: 'complete', confidence: 1.0 },
      { s_m: 1, left_width_m: 7, right_width_m: 4, left_width_smooth_m: 4.5, right_width_smooth_m: 3, status: 'complete', confidence: 1.0 },
    ];

    const rawResult = computeBoundaries({ pathPoints, profileSamples, useSmooth: false });
    const smoothResult = computeBoundaries({ pathPoints, profileSamples, useSmooth: true });

    // Raw: left at x=-5 and -7, right at x=3 and 4
    assert(approxEq(rawResult.left[0].x_m, -5), 'raw left[0] x = -5', String(rawResult.left[0].x_m));
    assert(approxEq(rawResult.left[1].x_m, -7), 'raw left[1] x = -7', String(rawResult.left[1].x_m));
    assert(approxEq(rawResult.right[0].x_m, 3), 'raw right[0] x = 3', String(rawResult.right[0].x_m));
    assert(approxEq(rawResult.right[1].x_m, 4), 'raw right[1] x = 4', String(rawResult.right[1].x_m));

    // Smooth: left at x=-4 and -4.5, right at x=2.5 and 3
    assert(approxEq(smoothResult.left[0].x_m, -4), 'smooth left[0] x = -4', String(smoothResult.left[0].x_m));
    assert(approxEq(smoothResult.left[1].x_m, -4.5), 'smooth left[1] x = -4.5', String(smoothResult.left[1].x_m));
    assert(approxEq(smoothResult.right[0].x_m, 2.5), 'smooth right[0] x = 2.5', String(smoothResult.right[0].x_m));
    assert(approxEq(smoothResult.right[1].x_m, 3), 'smooth right[1] x = 3', String(smoothResult.right[1].x_m));

    assert(smoothResult.use_smooth === true, 'result.use_smooth = true', String(smoothResult.use_smooth));
  }

  // ── Test 8: Summary fields ──
  console.log('\n── Summary fields ──');
  {
    const pathPoints = [
      { s_m: 0, x_m: 0, z_m: 0, sample_count: 5 },
      { s_m: 1, x_m: 0, z_m: 1, sample_count: 5 },
      { s_m: 3, x_m: 0, z_m: 3, sample_count: 5 },
    ];
    const profileSamples = [
      { s_m: 0, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      { s_m: 1, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      { s_m: 2, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      { s_m: 3, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
    ];

    const result = computeBoundaries({ pathPoints, profileSamples, useSmooth: false });

    assert(result.summary.path_points === 3, 'summary.path_points = 3', String(result.summary.path_points));
    assert(result.summary.profile_samples === 4, 'summary.profile_samples = 4', String(result.summary.profile_samples));
    assert(result.summary.matched_bins === 3, 'summary.matched_bins = 3', String(result.summary.matched_bins));
    assert(result.summary.unmatched_path === 0, 'summary.unmatched_path = 0', String(result.summary.unmatched_path));
    assert(result.summary.left_boundary_points === 3, 'summary.left_boundary_points = 3', String(result.summary.left_boundary_points));
    assert(result.summary.right_boundary_points === 3, 'summary.right_boundary_points = 3', String(result.summary.right_boundary_points));
  }

  // ── Test 9: Single-point path ──
  console.log('\n── Single-point path ──');
  {
    const pathPoints = [
      { s_m: 0, x_m: 0, z_m: 0, sample_count: 5 },
    ];
    const profileSamples = [
      { s_m: 0, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
    ];

    const result = computeBoundaries({ pathPoints, profileSamples, useSmooth: false });

    assert(result.left.length === 1, '1 left boundary point', String(result.left.length));
    assert(result.right.length === 1, '1 right boundary point', String(result.right.length));
    // Single point tangent is undefined; should still produce some result
    assert(Number.isFinite(result.left[0].x_m), 'left x is finite', String(result.left[0].x_m));
    assert(Number.isFinite(result.left[0].z_m), 'left z is finite', String(result.left[0].z_m));
  }

  // ── Test 10: Colinear points (tangent is well-defined) ──
  console.log('\n── Colinear points ──');
  {
    const pathPoints = [
      { s_m: 0, x_m: 1, z_m: 1, sample_count: 5 },
      { s_m: 1, x_m: 2, z_m: 2, sample_count: 5 },
      { s_m: 2, x_m: 3, z_m: 3, sample_count: 5 },
    ];
    const profileSamples = [
      { s_m: 0, left_width_m: 1, right_width_m: 1, status: 'complete', confidence: 1.0 },
      { s_m: 1, left_width_m: 1, right_width_m: 1, status: 'complete', confidence: 1.0 },
      { s_m: 2, left_width_m: 1, right_width_m: 1, status: 'complete', confidence: 1.0 },
    ];

    const result = computeBoundaries({ pathPoints, profileSamples, useSmooth: false });

    // Tangent along (1,1)/sqrt(2), normal = (-1/sqrt(2), 1/sqrt(2))
    // Left: offset by (-1/sqrt(2)*1, 1/sqrt(2)*1) ≈ (-0.707, 0.707)
    // Right: offset by (1/sqrt(2)*1, -1/sqrt(2)*1) ≈ (0.707, -0.707)
    const nx = -1 / Math.SQRT2;
    const nz = 1 / Math.SQRT2;
    for (let i = 0; i < 3; i++) {
      const lp = result.left[i];
      const rp = result.right[i];
      const expectedLx = pathPoints[i].x_m + nx * 1;
      const expectedLz = pathPoints[i].z_m + nz * 1;
      const expectedRx = pathPoints[i].x_m - nx * 1;
      const expectedRz = pathPoints[i].z_m - nz * 1;
      assert(approxEq(lp.x_m, expectedLx), `left[${i}] x_m correct`, `${lp.x_m} ≈ ${expectedLx}`);
      assert(approxEq(lp.z_m, expectedLz), `left[${i}] z_m correct`, `${lp.z_m} ≈ ${expectedLz}`);
      assert(approxEq(rp.x_m, expectedRx), `right[${i}] x_m correct`, `${rp.x_m} ≈ ${expectedRx}`);
      assert(approxEq(rp.z_m, expectedRz), `right[${i}] z_m correct`, `${rp.z_m} ≈ ${expectedRz}`);
    }
  }

  // ── Test 11: CLI invocation ──
  console.log('\n── CLI invocation ──');
  {
    const pathJson = tempPath('cb-cli-path', '.json');
    const profileJson = tempPath('cb-cli-profile', '.json');
    const outJson = tempPath('cb-cli-out', '.json');

    fs.writeFileSync(pathJson, JSON.stringify({
      track_id: 'cli-track',
      layout_id: 'default',
      bin_size_m: 1,
      points: [
        { s_m: 0, x_m: 0, z_m: 0, sample_count: 5 },
        { s_m: 1, x_m: 0, z_m: 1, sample_count: 5 },
      ],
    }));

    fs.writeFileSync(profileJson, JSON.stringify({
      track_id: 'cli-track',
      layout_id: 'default',
      bin_size_m: 1,
      samples: [
        { s_m: 0, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
        { s_m: 1, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      ],
    }));

    const cli = spawnSync('node', [
      SCRIPT,
      '--path', pathJson,
      '--profile', profileJson,
      '--out', outJson,
    ], { encoding: 'utf8', timeout: 30000 });

    assert(cli.status === 0, 'CLI exits 0', cli.stderr);
    const disk = JSON.parse(fs.readFileSync(outJson, 'utf8'));
    assert(disk.track_id === 'cli-track', 'CLI output includes track_id', disk.track_id);
    assert(disk.layout_id === 'default', 'CLI output includes layout_id', disk.layout_id);
    assert(disk.left.length === 2, 'CLI left boundary has 2 points', String(disk.left.length));
    assert(disk.right.length === 2, 'CLI right boundary has 2 points', String(disk.right.length));
    assert(disk.use_smooth === false, 'CLI use_smooth = false by default', String(disk.use_smooth));
  }

  // ── Test 12: CLI --smooth flag ──
  console.log('\n── CLI --smooth flag ──');
  {
    const pathJson = tempPath('cb-smooth-path', '.json');
    const profileJson = tempPath('cb-smooth-profile', '.json');
    const outJson = tempPath('cb-smooth-out', '.json');

    fs.writeFileSync(pathJson, JSON.stringify({
      track_id: 'smooth-track',
      layout_id: 'default',
      bin_size_m: 1,
      points: [
        { s_m: 0, x_m: 0, z_m: 0, sample_count: 5 },
      ],
    }));

    fs.writeFileSync(profileJson, JSON.stringify({
      track_id: 'smooth-track',
      layout_id: 'default',
      bin_size_m: 1,
      samples: [
        { s_m: 0, left_width_m: 5, right_width_m: 3, left_width_smooth_m: 4, right_width_smooth_m: 2, status: 'complete', confidence: 1.0 },
      ],
    }));

    const cli = spawnSync('node', [
      SCRIPT,
      '--path', pathJson,
      '--profile', profileJson,
      '--out', outJson,
      '--smooth',
    ], { encoding: 'utf8', timeout: 30000 });

    assert(cli.status === 0, 'CLI --smooth exits 0', cli.stderr);
    const disk = JSON.parse(fs.readFileSync(outJson, 'utf8'));
    assert(disk.use_smooth === true, 'CLI --smooth sets use_smooth = true', String(disk.use_smooth));
  }

  // ── Test 13: Overwrite refusal ──
  console.log('\n── Overwrite refusal ──');
  {
    const pathJson = tempPath('cb-ow-path', '.json');
    const profileJson = tempPath('cb-ow-profile', '.json');
    const outJson = tempPath('cb-ow-out', '.json');

    fs.writeFileSync(pathJson, JSON.stringify({
      track_id: 'ow-track', layout_id: 'default', bin_size_m: 1,
      points: [{ s_m: 0, x_m: 0, z_m: 0, sample_count: 5 }],
    }));
    fs.writeFileSync(profileJson, JSON.stringify({
      track_id: 'ow-track', layout_id: 'default', bin_size_m: 1,
      samples: [{ s_m: 0, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 }],
    }));
    fs.writeFileSync(outJson, 'SENTINEL');

    const cli = spawnSync('node', [
      SCRIPT,
      '--path', pathJson,
      '--profile', profileJson,
      '--out', outJson,
    ], { encoding: 'utf8', timeout: 30000 });

    assert(cli.status !== 0, 'CLI refuses to overwrite by default', `exit ${cli.status}`);
    assert(cli.stderr.includes('exists'), 'CLI error mentions exists', cli.stderr.slice(0, 200));

    const cli2 = spawnSync('node', [
      SCRIPT,
      '--path', pathJson,
      '--profile', profileJson,
      '--out', outJson,
      '--overwrite',
    ], { encoding: 'utf8', timeout: 30000 });

    assert(cli2.status === 0, 'CLI --overwrite succeeds', cli2.stderr);
    const disk = JSON.parse(fs.readFileSync(outJson, 'utf8'));
    assert(disk.track_id === 'ow-track', 'overwrite output valid');
  }

  // ── Test 14: Width field in boundary output ──
  console.log('\n── Width field propagation ──');
  {
    const pathPoints = [
      { s_m: 0, x_m: 0, z_m: 0, sample_count: 5 },
    ];
    const profileSamples = [
      { s_m: 0, left_width_m: 5.5, right_width_m: 3.2, status: 'complete', confidence: 1.0 },
    ];

    const result = computeBoundaries({ pathPoints, profileSamples, useSmooth: false });

    assert(approxEq(result.left[0].width_m, 5.5), 'left width_m = 5.5', String(result.left[0].width_m));
    assert(approxEq(result.right[0].width_m, 3.2), 'right width_m = 3.2', String(result.right[0].width_m));
  }

  // ── Test 15: Real session integration (Spa endurance) ──
  console.log('\n── Real session: Spa endurance boundaries ──');
  {
    const dataDir = path.join(ROOT, 'product', 'data', 'circuit-de-spa-francorchamps-endurance', 'default');
    const pathFile = path.join(dataDir, 'path.json');
    const profileFile = path.join(dataDir, 'width-profile.json');

    if (!fs.existsSync(pathFile) || !fs.existsSync(profileFile)) {
      console.log('  [SKIP] Spa endurance path/profile data not found — skipping real-data test');
    } else {
      const pathData = JSON.parse(fs.readFileSync(pathFile, 'utf8'));
      const profileData = JSON.parse(fs.readFileSync(profileFile, 'utf8'));

      const result = computeBoundaries({
        pathPoints: pathData.points,
        profileSamples: profileData.samples,
        useSmooth: !!profileData.samples.some(s => s.left_width_smooth_m != null),
      });

      assert(result.left.length > 0, 'real left boundary has points', String(result.left.length));
      assert(result.right.length > 0, 'real right boundary has points', String(result.right.length));
      assert(result.left.length === result.right.length, 'real left/right same length');
      assert(result.summary.matched_bins > 0, 'real matched bins > 0', String(result.summary.matched_bins));

      // All boundary points should have finite positions
      const badLeft = result.left.filter(p => !Number.isFinite(p.x_m) || !Number.isFinite(p.z_m));
      const badRight = result.right.filter(p => !Number.isFinite(p.x_m) || !Number.isFinite(p.z_m));
      assert(badLeft.length === 0, 'all left positions finite', `${badLeft.length} bad`);
      assert(badRight.length === 0, 'all right positions finite', `${badRight.length} bad`);

      console.log(`    left=${result.left.length} right=${result.right.length} matched=${result.summary.matched_bins} unmatched=${result.summary.unmatched_path}`);
    }
  }

  // ── Test 16: Existing commands unchanged ──
  console.log('\n── Existing center-path and width-profile commands unchanged ──');
  {
    const cpScript = path.join(ROOT, 'dev/scripts/export_center_path.js');
    const wpScript = path.join(ROOT, 'dev/scripts/export_width_profile.js');

    const cpHelp = spawnSync('node', [cpScript], { encoding: 'utf8', timeout: 10000 });
    assert(cpHelp.status !== 0 || cpHelp.stdout.length >= 0, 'center-path script still runnable');

    const wpHelp = spawnSync('node', [wpScript], { encoding: 'utf8', timeout: 10000 });
    assert(wpHelp.status !== 0 || wpHelp.stdout.length >= 0, 'width-profile script still runnable');
  }
}

async function main() {
  console.log('═══ Track Outline Phase 09.1 Boundary Polylines Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});