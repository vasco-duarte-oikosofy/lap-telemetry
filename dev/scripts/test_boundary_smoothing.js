/**
 * Track outline Phase 09.2 — Boundary polyline smoothing tests.
 *
 * Run: node scripts/test_boundary_smoothing.js
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

function writeFixture(dir, name, data) {
  const p = path.join(dir, `${name}.json`);
  fs.writeFileSync(p, JSON.stringify(data));
  return p;
}

/** Make a simple 3-point path/profile fixture for CLI tests */
function simpleFixture(trackId) {
  return {
    path: {
      track_id: trackId, layout_id: 'default', bin_size_m: 1,
      points: [
        { s_m: 0, x_m: 0, z_m: 0, sample_count: 5 },
        { s_m: 1, x_m: 0, z_m: 1, sample_count: 5 },
        { s_m: 2, x_m: 0, z_m: 2, sample_count: 5 },
      ],
    },
    profile: {
      track_id: trackId, layout_id: 'default', bin_size_m: 1,
      samples: [
        { s_m: 0, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
        { s_m: 1, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
        { s_m: 2, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
      ],
    },
  };
}

async function runTests() {
  const { computeBoundaries, smoothBoundary } = require(SCRIPT);

  // ── Test 1: Straight-line identity ──
  console.log('\n── Straight-line identity ──');
  {
    const pts = Array.from({ length: 50 }, (_, i) =>
      ({ s_m: i, x_m: 5, z_m: i, width_m: 5, status: 'complete', confidence: 1.0 }));
    const smoothed = smoothBoundary(pts, 5);
    assert(smoothed.length === pts.length, 'same number of points');
    // Constant x_m must remain exactly 5 under averaging
    const allX5 = smoothed.every(p => approxEq(p.x_m, 5, 0.01));
    assert(allX5, 'all x_m ≈ 5 (constant preserved)');
    const allZOriginal = smoothed.every((p, i) => approxEq(p.z_m, i, 0.01));
    assert(allZOriginal, 'all z_m ≈ original (straight line preserved)');
  }

  // ── Test 2: Jittered boundary → smoothing reduces max deviation ──
  console.log('\n── Jittered boundary: smoothing reduces deviation ──');
  {
    const trueX = 5, amp = 2.0, freq = 1.5;
    const raw = Array.from({ length: 100 }, (_, i) =>
      ({ s_m: i, x_m: trueX + amp * Math.sin(i * freq), z_m: i, width_m: 5, status: 'complete', confidence: 1.0 }));
    const rawMaxDev = Math.max(...raw.map(p => Math.abs(p.x_m - trueX)));
    assert(rawMaxDev > amp * 0.9, 'raw has significant deviation');
    const smoothed = smoothBoundary(raw, 5);
    const smoothMaxDev = Math.max(...smoothed.map(p => Math.abs(p.x_m - trueX)));
    assert(smoothMaxDev < rawMaxDev, 'smoothed deviation < raw', `smooth=${smoothMaxDev.toFixed(4)} raw=${rawMaxDev.toFixed(4)}`);
    assert(smoothMaxDev < rawMaxDev * 0.75, 'smoothed deviation < 75% of raw');
  }

  // ── Test 3: Circular arc preservation ──
  console.log('\n── Circular arc: radius preserved after smoothing ──');
  {
    const R = 100, n = 40;
    const pts = Array.from({ length: n + 1 }, (_, i) => {
      const angle = (i / n) * Math.PI / 2;
      return { s_m: i, x_m: R - R * Math.cos(angle), z_m: R * Math.sin(angle), width_m: 5, status: 'complete', confidence: 1.0 };
    });
    const avgR = (arr) => arr.reduce((s, p) => s + Math.sqrt((p.x_m - R) ** 2 + p.z_m ** 2), 0) / arr.length;
    const rawAvg = avgR(pts);
    const smoothAvg = avgR(smoothBoundary(pts, 5));
    assert(Math.abs(smoothAvg - rawAvg) < 0.5, `radius change < 0.5m`, `Δ=${Math.abs(smoothAvg - rawAvg).toFixed(4)}m`);
  }

  // ── Test 4: Zero-width barrier points stay at center ──
  console.log('\n── Zero-width barrier points ──');
  {
    const pts = Array.from({ length: 11 }, (_, i) => {
      const isBarrier = i === 5;
      const sideX = i < 5 ? 5 : 20;
      return { s_m: i, x_m: isBarrier ? 0 : sideX, z_m: i, width_m: isBarrier ? 0 : 5, status: 'complete', confidence: 1.0 };
    });
    const smoothed = smoothBoundary(pts, 5);
    assert(approxEq(smoothed[5].x_m, 0, 0.01), 'barrier x ≈ 0');
    assert(approxEq(smoothed[5].z_m, 5, 0.01), 'barrier z ≈ 5');
    assert(smoothed.slice(0, 5).every(p => approxEq(p.x_m, 5, 0.1)), 'left segment not pulled across barrier');
    assert(smoothed.slice(6).every(p => approxEq(p.x_m, 20, 0.1)), 'right segment not pulled across barrier');
  }

  // ── Test 5: Gap handling — smoothing does not bridge gaps ──
  console.log('\n── Gap handling: no bridging across s_m gaps ──');
  {
    const make = (s, x, z) => ({ s_m: s, x_m: x, z_m: z, width_m: 5, status: 'complete', confidence: 1.0 });
    const pts = [make(0,5,0), make(1,5,1), make(2,5,2), make(3,5,3), make(4,5,4),
                 make(20,10,20), make(21,10,21), make(22,10,22), make(23,10,23), make(24,10,24)];
    const smoothed = smoothBoundary(pts, 5, 1);
    const seg1_ok = smoothed.slice(0, 5).every(p => approxEq(p.x_m, 5, 0.1));
    const seg2_ok = smoothed.slice(5).every(p => approxEq(p.x_m, 10, 0.1));
    assert(seg1_ok, 'segment 1 (s=0..4) stays at x≈5');
    assert(seg2_ok, 'segment 2 (s=20..24) stays at x≈10');
  }

  // ── Test 6: Window=1 and Window=0 are identity ──
  console.log('\n── Window=1 and Window=0 are identity ──');
  {
    const pts = Array.from({ length: 20 }, (_, i) =>
      ({ s_m: i, x_m: 5 + Math.sin(i) * 2, z_m: i * 2, width_m: 5, status: 'complete', confidence: 1.0 }));
    const w1 = smoothBoundary(pts, 1);
    const w1ok = w1.every((p, i) => approxEq(p.x_m, pts[i].x_m) && approxEq(p.z_m, pts[i].z_m));
    assert(w1ok, 'window=1 returns original values');

    // window=0 via computeBoundaries
    const pp = [{ s_m: 0, x_m: 0, z_m: 0, sample_count: 1 }];
    const ps = [{ s_m: 0, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 }];
    const r0 = computeBoundaries({ pathPoints: pp, profileSamples: ps, useSmooth: false });
    const r0s = computeBoundaries({ pathPoints: pp, profileSamples: ps, useSmooth: false, smoothBoundaryWindow: 0 });
    assert(approxEq(r0s.left[0].x_m, r0.left[0].x_m), 'smoothBoundaryWindow=0 left x unchanged');
    assert(r0.smooth_boundary_window === 0, 'default smooth_boundary_window = 0');
  }

  // ── Test 7: Integration with computeBoundaries ──
  console.log('\n── computeBoundaries with smoothBoundaryWindow ──');
  {
    const pp = Array.from({ length: 30 }, (_, i) => ({ s_m: i, x_m: Math.sin(i * 0.3) * 2, z_m: i, sample_count: 10 }));
    const ps = Array.from({ length: 30 }, (_, i) => ({ s_m: i, left_width_m: 5, right_width_m: 5, status: 'complete', confidence: 1.0 }));
    const raw = computeBoundaries({ pathPoints: pp, profileSamples: ps, useSmooth: false });
    const smooth = computeBoundaries({ pathPoints: pp, profileSamples: ps, useSmooth: false, smoothBoundaryWindow: 5 });

    assert(smooth.left.length === raw.left.length, 'same left point count');
    assert(smooth.right.length === raw.right.length, 'same right point count');
    assert(smooth.smooth_boundary_window === 5, 'smooth_boundary_window = 5');
    assert(raw.smooth_boundary_window === 0, 'raw smooth_boundary_window = 0');

    const different = smooth.left.some((p, i) =>
      !approxEq(p.x_m, raw.left[i].x_m) || !approxEq(p.z_m, raw.left[i].z_m));
    assert(different, 'smoothed positions differ from raw');

    // Metadata unchanged
    const metaOK = smooth.left.every((p, i) =>
      approxEq(p.width_m, raw.left[i].width_m) &&
      p.status === raw.left[i].status &&
      approxEq(p.confidence, raw.left[i].confidence));
    assert(metaOK, 'width, status, confidence unchanged');
  }

  // ── Test 8: CLI --smooth-boundary ──
  console.log('\n── CLI --smooth-boundary and combined flags ──');
  {
    const fix = simpleFixture('sb-cli');
    const outJson = tempPath('sb-cli', '.json');
    const tmpDir = path.dirname(outJson);

    const pathJson = writeFixture(tmpDir, 'path-sb', fix.path);
    const profileJson = writeFixture(tmpDir, 'prof-sb', fix.profile);

    // Default: smooth_boundary_window = 0
    const cli1 = spawnSync('node', [SCRIPT, '--path', pathJson, '--profile', profileJson, '--out', outJson, '--overwrite'],
      { encoding: 'utf8', timeout: 30000 });
    assert(cli1.status === 0, 'CLI default exits 0', cli1.stderr);
    const d1 = JSON.parse(fs.readFileSync(outJson, 'utf8'));
    assert(d1.smooth_boundary_window === 0, 'default smooth_boundary_window = 0');

    // With --smooth-boundary 5
    const cli2 = spawnSync('node', [SCRIPT, '--path', pathJson, '--profile', profileJson, '--out', outJson, '--overwrite', '--smooth-boundary', '5'],
      { encoding: 'utf8', timeout: 30000 });
    assert(cli2.status === 0, 'CLI --smooth-boundary 5 exits 0', cli2.stderr);
    const d2 = JSON.parse(fs.readFileSync(outJson, 'utf8'));
    assert(d2.smooth_boundary_window === 5, 'smooth_boundary_window = 5');

    // Combined --smooth --smooth-boundary 3
    const fix2 = { ...fix, profile: { ...fix.profile, samples: fix.profile.samples.map(s => ({ ...s, left_width_smooth_m: s.left_width_m - 1, right_width_smooth_m: s.right_width_m - 0.5 })) } };
    const prof2 = writeFixture(tmpDir, 'prof-sb2', fix2.profile);
    const cli3 = spawnSync('node', [SCRIPT, '--path', pathJson, '--profile', prof2, '--out', outJson, '--overwrite', '--smooth', '--smooth-boundary', '3'],
      { encoding: 'utf8', timeout: 30000 });
    assert(cli3.status === 0, 'CLI --smooth --smooth-boundary 3 exits 0', cli3.stderr);
    const d3 = JSON.parse(fs.readFileSync(outJson, 'utf8'));
    assert(d3.use_smooth === true, 'combined: use_smooth = true');
    assert(d3.smooth_boundary_window === 3, 'combined: smooth_boundary_window = 3');
  }

  // ── Test 9: Existing computeBoundaries unchanged ──
  console.log('\n── Existing computeBoundaries calls unchanged ──');
  {
    const pp = [{ s_m: 0, x_m: 0, z_m: 0, sample_count: 5 }, { s_m: 1, x_m: 0, z_m: 1, sample_count: 5 }];
    const ps = [{ s_m: 0, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 },
                { s_m: 1, left_width_m: 5, right_width_m: 3, status: 'complete', confidence: 1.0 }];
    const result = computeBoundaries({ pathPoints: pp, profileSamples: ps, useSmooth: false });
    assert(approxEq(result.left[0].x_m, -5), 'left[0] x = -5 (unchanged)');
    assert(approxEq(result.left[0].z_m, 0), 'left[0] z = 0 (unchanged)');
    assert(result.smooth_boundary_window === 0, 'default smooth_boundary_window = 0');
  }

  // ── Test 10: Real Spa data integration ──
  console.log('\n── Real Spa data: boundary smoothing integration ──');
  {
    const dataDir = path.join(ROOT, 'product', 'data', 'circuit-de-spa-francorchamps-endurance', 'default');
    const pathFile = path.join(dataDir, 'path.json');
    const profileFile = path.join(dataDir, 'width-profile.json');

    if (!fs.existsSync(pathFile) || !fs.existsSync(profileFile)) {
      console.log('  [SKIP] Spa endurance data not found');
    } else {
      const pathData = JSON.parse(fs.readFileSync(pathFile, 'utf8'));
      const profileData = JSON.parse(fs.readFileSync(profileFile, 'utf8'));
      const args = { pathPoints: pathData.points, profileSamples: profileData.samples, useSmooth: true };
      const raw = computeBoundaries(args);
      const smooth = computeBoundaries({ ...args, smoothBoundaryWindow: 5 });

      assert(smooth.left.length === raw.left.length, 'same left point count');
      assert(smooth.right.length === raw.right.length, 'same right point count');
      assert(smooth.left.every(p => Number.isFinite(p.x_m) && Number.isFinite(p.z_m)), 'all left positions finite');
      assert(smooth.right.every(p => Number.isFinite(p.x_m) && Number.isFinite(p.z_m)), 'all right positions finite');

      // Zero-width points stay at path
      const zPreserved = raw.left.every((r, i) =>
        r.width_m !== 0 || (approxEq(smooth.left[i].x_m, r.x_m, 0.01) && approxEq(smooth.left[i].z_m, r.z_m, 0.01))
      );
      assert(zPreserved, 'zero-width left boundary points preserved');

      // Smoothed has less jerk
      const jerk = (arr) => arr.slice(1, -1).reduce((s, p, i) =>
        s + Math.abs(arr[i + 2].x_m - 2 * p.x_m + arr[i].x_m), 0);
      assert(jerk(smooth.left) < jerk(raw.left), 'smoothed left has less jerk than raw');
    }
  }

  // ── Test 11: Gap with custom binSize ──
  console.log('\n── Gap in s_m with custom binSize ──');
  {
    const make = (s, x, z) => ({ s_m: s, x_m: x, z_m: z, width_m: 5, status: 'complete', confidence: 1.0 });
    const pts = [make(0,5,0), make(5,5,5), make(10,5,10), make(50,15,50), make(55,15,55)];
    const smoothed = smoothBoundary(pts, 5, 5); // binSize=5 → gap>10 is break
    assert(smoothed.slice(0, 3).every(p => approxEq(p.x_m, 5, 0.1)), 'seg1 x ≈ 5');
    assert(smoothed.slice(3).every(p => approxEq(p.x_m, 15, 0.1)), 'seg2 x ≈ 15');
  }

  // ── Test 12: Non-zero-width points near barriers ──
  console.log('\n── Non-zero-width points near barriers ──');
  {
    const pts = Array.from({ length: 11 }, (_, i) => {
      const isBarrier = i === 5;
      return { s_m: i, x_m: isBarrier ? 0 : 5, z_m: i, width_m: isBarrier ? 0 : 5, status: 'complete', confidence: 1.0 };
    });
    const smoothed = smoothBoundary(pts, 2);
    assert(approxEq(smoothed[5].x_m, 0, 0.001), 'barrier stays at x=0');
    assert(smoothed.every(p => Number.isFinite(p.x_m) && Number.isFinite(p.z_m)), 'all positions finite');
  }
}

async function main() {
  console.log('═══ Track Outline Phase 09.2 Boundary Smoothing Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});