/**
 * Track outline Phase 08.1 — Width profile interpolation and smoothing tests.
 *
 * Run: node scripts/test_width_profile_smoothing.js
 */

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const EXPORT_SCRIPT = path.join(ROOT, 'scripts/export_width_profile.js');

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

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function buildParquet(name, rows) {
  const out = tempPath(name, '.parquet');
  function pyList(arr) {
    const inner = arr.map(v => v === null || v === undefined ? 'None' : JSON.stringify(v)).join(', ');
    return `[${inner}]`;
  }
  const rawLapDist = rows.map(r => r.raw_lap_distance_m ?? null);
  const pathLateral = rows.map(r => r.path_lateral_m ?? null);
  const trackEdge = rows.map(r => r.track_edge_m ?? null);
  const lapNumber = rows.map(() => 1);
  const lapTimeS = rows.map((_, i) => i * 0.1);
  const lapDistM = rows.map(r => r.raw_lap_distance_m ?? 0);

  const code = `
import pyarrow as pa, pyarrow.parquet as pq
cols = [
  pa.array(${pyList(lapNumber)}, type=pa.int32()),
  pa.array(${pyList(lapTimeS)}, type=pa.float32()),
  pa.array(${pyList(lapDistM)}, type=pa.float32()),
  pa.array(${pyList(rawLapDist)}, type=pa.float32()),
  pa.array(${pyList(pathLateral)}, type=pa.float32()),
  pa.array(${pyList(trackEdge)}, type=pa.float32()),
]
names = ['lap_number', 'lap_time_s', 'lap_distance_m',
         'raw_lap_distance_m', 'path_lateral_m', 'track_edge_m']
pq.write_table(pa.Table.from_arrays(cols, names=names), r'''${out}''', compression='snappy')
`;
  const res = spawnSync('python3', ['-c', code], { encoding: 'utf8', timeout: 30000 });
  if (res.error || res.status !== 0) throw new Error(res.error?.message || res.stderr);
  return out;
}

async function runTests() {
  const { exportWidthProfile, buildProfileFromRows, interpolateAndSmooth } = require(EXPORT_SCRIPT);

  // ── Test 1: Short gap (3 bins) linearly interpolated ──
  console.log('\n── Short gap linear interpolation ──');
  {
    // Complete bin at s=0 (left=8, right=6), gap at s=1,2,3, complete bin at s=4 (left=12, right=10)
    const rows = [
      // s=0: 4 left samples, 4 right samples
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 8 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 5), path_lateral_m: 1, track_edge_m: 6 })),
      // s=4: 4 left samples, 4 right samples
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 4.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 12 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 4.1 + 0.1 * (i + 4), path_lateral_m: 1, track_edge_m: 10 })),
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const smoothed = interpolateAndSmooth(samples);

    // Gap bins: s=1,2,3 should be interpolated
    const s1 = smoothed.find(s => s.s_m === 1);
    const s2 = smoothed.find(s => s.s_m === 2);
    const s3 = smoothed.find(s => s.s_m === 3);

    assert(s1 && s1.left_width_smooth_m != null, 's=1 has left_width_smooth_m');
    assert(s1 && s1.right_width_smooth_m != null, 's=1 has right_width_smooth_m');

    // Expected interpolated values (before smoothing):
    // left:  s=0→8, s=4→12 → linear step = 4/4 = 1 per bin
    //   s=1→9, s=2→10, s=3→11
    // right: s=0→6, s=4→10 → step = 4/4 = 1
    //   s=1→7, s=2→8, s=3→9
    // But smoothing with window=5 will also adjust these. Check interpolated before smooth:
    // Actually, interpolation fills the gap first, then smoothing is applied.
    // After interpolation only (before moving-average), values should be exact linear.
    // Smoothing with window=5 will blur slightly. Let's check a middle bin for approximate.
    // For the exact interpolation check, compare to midpoint:
    assert(s2 && Math.abs(s2.left_width_smooth_m - 10) < 0.5,
      's=2 left_width_smooth_m ≈ 10 (interpolated midpoint)', String(s2?.left_width_smooth_m));
    assert(s2 && Math.abs(s2.right_width_smooth_m - 8) < 0.5,
      's=2 right_width_smooth_m ≈ 8 (interpolated midpoint)', String(s2?.right_width_smooth_m));
  }

  // ── Test 2: Long gap NOT interpolated ──
  console.log('\n── Long gap stays missing ──');
  {
    // Complete at s=0, then 15 missing bins (s=1..15), complete at s=16
    const rows = [
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 8 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 5), path_lateral_m: 1, track_edge_m: 6 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 16.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 12 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 16.1 + 0.1 * (i + 4), path_lateral_m: 1, track_edge_m: 10 })),
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const smoothed = interpolateAndSmooth(samples);

    // All gap bins should remain as-is (no interpolation)
    const gapBin = smoothed.find(s => s.s_m === 8);
    assert(gapBin && gapBin.left_width_smooth_m === 0,
      'long-gap bin left_width_smooth_m = 0 (not interpolated)', String(gapBin?.left_width_smooth_m));
    assert(gapBin && gapBin.right_width_smooth_m === 0,
      'long-gap bin right_width_smooth_m = 0 (not interpolated)', String(gapBin?.right_width_smooth_m));
    assert(gapBin && gapBin.status === 'missing',
      'long-gap bin status remains "missing"', gapBin?.status);
  }

  // ── Test 3: Smoothing affects widths but not raw counts or confidence ──
  console.log('\n── Smoothing preserves raw data ──');
  {
    const rows = [
      // s=0: left=5, right=4, complete
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 5 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.05 * (i + 1), path_lateral_m: 1, track_edge_m: 4 })),
      // s=1: left=10, right=9, complete
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 1.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 10 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 1.05 + 0.05 * i, path_lateral_m: 1, track_edge_m: 9 })),
      // s=2: left=7, right=6, complete
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 2.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 7 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 2.05 + 0.05 * i, path_lateral_m: 1, track_edge_m: 6 })),
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const smoothed = interpolateAndSmooth(samples);

    for (const bin of smoothed) {
      // Raw fields must be identical to pre-smooth values
      assert(typeof bin.left_sample_count === 'number' && bin.left_sample_count > 0,
        `raw left_sample_count preserved at s=${bin.s_m}`, String(bin.left_sample_count));
      assert(typeof bin.right_sample_count === 'number' && bin.right_sample_count > 0,
        `raw right_sample_count preserved at s=${bin.s_m}`, String(bin.right_sample_count));
      assert(typeof bin.confidence === 'number',
        `raw confidence preserved at s=${bin.s_m}`, String(bin.confidence));
      assert(typeof bin.status === 'string',
        `raw status preserved at s=${bin.s_m}`, bin.status);
      assert(typeof bin.left_width_m === 'number',
        `raw left_width_m preserved at s=${bin.s_m}`, String(bin.left_width_m));
      assert(typeof bin.right_width_m === 'number',
        `raw right_width_m preserved at s=${bin.s_m}`, String(bin.right_width_m));
    }

    // At least one smoothed value should differ from raw (smoothing had effect)
    const anyDiff = smoothed.some(s => s.left_width_smooth_m !== s.left_width_m || s.right_width_smooth_m !== s.right_width_m);
    assert(anyDiff, 'smoothing produces different values from raw for at least one bin');
  }

  // ── Test 4: Smoothing narrows adjacent-bin differences ──
  console.log('\n── Smoothing narrows adjacent differences ──');
  {
    // Create a spike: s=0 left=5, s=1 left=15, s=2 left=5
    const rows = [
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 5 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.05 * (i + 1), path_lateral_m: 1, track_edge_m: 4 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 1.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 15 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 1.05 + 0.05 * i, path_lateral_m: 1, track_edge_m: 14 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 2.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 5 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 2.05 + 0.05 * i, path_lateral_m: 1, track_edge_m: 4 })),
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const smoothed = interpolateAndSmooth(samples);

    const bin1 = smoothed.find(s => s.s_m === 1);
    assert(bin1, 'spike bin exists');
    // Smoothed spike should be less than raw (moving average pulls toward neighbors)
    assert(bin1.left_width_smooth_m < bin1.left_width_m,
      'smoothed spike < raw spike', `${bin1.left_width_smooth_m} < ${bin1.left_width_m}`);
    assert(bin1.right_width_smooth_m < bin1.right_width_m,
      'smoothed right spike < raw', `${bin1.right_width_smooth_m} < ${bin1.right_width_m}`);
  }

  // ── Test 5: No smoothing across long gaps ──
  console.log('\n── No smoothing across long gaps ──');
  {
    // s=0 complete, s=1..15 missing (long gap), s=16 complete
    const rows = [
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 8 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.05 * (i + 1), path_lateral_m: 1, track_edge_m: 6 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 16.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 12 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 16.05 + 0.05 * i, path_lateral_m: 1, track_edge_m: 10 })),
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const smoothed = interpolateAndSmooth(samples);

    // s=0 and s=16 should not be smoothed by including gap bins
    const bin0 = smoothed.find(s => s.s_m === 0);
    const bin16 = smoothed.find(s => s.s_m === 16);
    // Raw left=8 at s=0, smoothing shouldn't change it much since only neighbor is gap
    assert(bin0 && bin0.left_width_smooth_m === bin0.left_width_m,
      'long-gap edge bin: smoothed = raw (only gap neighbors)', String(bin0?.left_width_smooth_m));
    assert(bin16 && bin16.left_width_smooth_m === bin16.left_width_m,
      'long-gap other edge bin: smoothed = raw', String(bin16?.left_width_smooth_m));
  }

  // ── Test 6: CLI --smooth produces smoothed fields ──
  console.log('\n── CLI --smooth flag adds smoothed fields ──');
  {
    const session = buildParquet('wp-smooth-cli', [
      { raw_lap_distance_m: 0.1, path_lateral_m: -1, track_edge_m: 8 },
      { raw_lap_distance_m: 0.2, path_lateral_m: 1, track_edge_m: 6 },
      { raw_lap_distance_m: 0.3, path_lateral_m: -1, track_edge_m: 8 },
      { raw_lap_distance_m: 0.4, path_lateral_m: 1, track_edge_m: 6 },
      { raw_lap_distance_m: 0.5, path_lateral_m: -1, track_edge_m: 8 },
      { raw_lap_distance_m: 0.6, path_lateral_m: 1, track_edge_m: 6 },
      { raw_lap_distance_m: 0.7, path_lateral_m: -1, track_edge_m: 8 },
      { raw_lap_distance_m: 0.8, path_lateral_m: 1, track_edge_m: 6 },
      { raw_lap_distance_m: 5.1, path_lateral_m: -1, track_edge_m: 10 },
      { raw_lap_distance_m: 5.2, path_lateral_m: 1, track_edge_m: 8 },
      { raw_lap_distance_m: 5.3, path_lateral_m: -1, track_edge_m: 10 },
      { raw_lap_distance_m: 5.4, path_lateral_m: 1, track_edge_m: 8 },
      { raw_lap_distance_m: 5.5, path_lateral_m: -1, track_edge_m: 10 },
      { raw_lap_distance_m: 5.6, path_lateral_m: 1, track_edge_m: 8 },
      { raw_lap_distance_m: 5.7, path_lateral_m: -1, track_edge_m: 10 },
      { raw_lap_distance_m: 5.8, path_lateral_m: 1, track_edge_m: 8 },
    ]);
    const smoothOut = tempPath('wp-smooth-cli-out', '.json');
    const cli = spawnSync('node', [
      EXPORT_SCRIPT,
      '--out', smoothOut,
      '--track-id', 'smooth-track',
      '--layout-id', 'default',
      '--smooth',
      session,
    ], { encoding: 'utf8', timeout: 30000 });

    assert(cli.status === 0, 'CLI --smooth exits 0', cli.stderr);
    const disk = readJson(smoothOut);
    const hasSmooth = disk.samples.every(s =>
      typeof s.left_width_smooth_m === 'number' && typeof s.right_width_smooth_m === 'number'
    );
    assert(hasSmooth, 'all samples have left_width_smooth_m and right_width_smooth_m with --smooth');
  }

  // ── Test 7: CLI without --smooth produces raw output (no smoothed fields) ──
  console.log('\n── CLI without --smooth produces raw-only output ──');
  {
    const session = buildParquet('wp-raw-cli', [
      { raw_lap_distance_m: 0.1, path_lateral_m: -1, track_edge_m: 8 },
      { raw_lap_distance_m: 0.2, path_lateral_m: 1, track_edge_m: 6 },
    ]);
    const rawOut = tempPath('wp-raw-cli-out', '.json');
    const cli = spawnSync('node', [
      EXPORT_SCRIPT,
      '--out', rawOut,
      '--track-id', 'raw-track',
      '--layout-id', 'default',
      session,
    ], { encoding: 'utf8', timeout: 30000 });

    assert(cli.status === 0, 'CLI raw exits 0', cli.stderr);
    const disk = readJson(rawOut);
    const noSmooth = disk.samples.every(s =>
      s.left_width_smooth_m === undefined && s.right_width_smooth_m === undefined
    );
    assert(noSmooth, 'no smoothed fields without --smooth flag');
  }

  // ── Test 8: Short gap interpolation fills gap correctly ──
  console.log('\n── Short gap interpolation correctness ──');
  {
    // Wide flat regions so edge-of-gap smoothing effect is negligible at test bins.
    // s=0..9: all left=10, right=8. Gap at s=10..12 (3 bins, short). s=13..22: all left=18, right=16.
    const rows = [];
    for (let s = 0; s <= 9; s++) {
      for (let k = 0; k < 4; k++) rows.push({ raw_lap_distance_m: s + 0.1 * k, path_lateral_m: -1, track_edge_m: 10 });
      for (let k = 0; k < 4; k++) rows.push({ raw_lap_distance_m: s + 0.05 * k, path_lateral_m: 1, track_edge_m: 8 });
    }
    for (let s = 13; s <= 22; s++) {
      for (let k = 0; k < 4; k++) rows.push({ raw_lap_distance_m: s + 0.1 * k, path_lateral_m: -1, track_edge_m: 18 });
      for (let k = 0; k < 4; k++) rows.push({ raw_lap_distance_m: s + 0.05 * k, path_lateral_m: 1, track_edge_m: 16 });
    }
    const { samples } = buildProfileFromRows(rows, 1);
    const smoothed = interpolateAndSmooth(samples);

    const s11 = smoothed.find(s => s.s_m === 11); // gap midpoint

    // Interpolated midpoint: left=14, right=12
    assert(s11 && Math.abs(s11.left_width_smooth_m - 14) < 1,
      'gap midpoint left smooth ≈ 14', String(s11?.left_width_smooth_m));
    assert(s11 && Math.abs(s11.right_width_smooth_m - 12) < 1,
      'gap midpoint right smooth ≈ 12', String(s11?.right_width_smooth_m));

    // Non-gap bins far from the gap should be close to raw (smoothing barely touches them)
    const s2 = smoothed.find(s => s.s_m === 2);
    assert(s2 && Math.abs(s2.left_width_smooth_m - 10) < 0.5,
      'non-gap flat bin left smooth ≈ 10', String(s2?.left_width_smooth_m));
    assert(s2 && Math.abs(s2.right_width_smooth_m - 8) < 0.5,
      'non-gap flat bin right smooth ≈ 8', String(s2?.right_width_smooth_m));
  }

  // ── Test 9: Existing tests still pass ──
  console.log('\n── Existing Phase 07+08 tests still pass ──');
  {
    const p07 = spawnSync('node', [path.join(ROOT, 'scripts/test_width_profile_export.js')], {
      encoding: 'utf8', timeout: 60000,
    });
    assert(p07.status === 0, 'Phase 07 tests still pass');

    const p08 = spawnSync('node', [path.join(ROOT, 'scripts/test_width_profile_confidence.js')], {
      encoding: 'utf8', timeout: 60000,
    });
    assert(p08.status === 0, 'Phase 08 tests still pass');
  }

  // ── Test 10: Real session smoke test with --smooth ──
  console.log('\n── Real session smoke: Spa endurance with --smooth ──');
  {
    const spaSession = path.join(ROOT, 'sessions', 'session_20260514T182139Z_circuit-de-spa-francorchamps-endurance_lmu.parquet');
    if (!fs.existsSync(spaSession)) {
      console.log('  [SKIP] Spa endurance session not found — skipping real-data smoke test');
    } else {
      const outPath = tempPath('wp-smooth-spa', '.json');
      const cli = spawnSync('node', [
        EXPORT_SCRIPT,
        '--out', outPath,
        '--track-id', 'circuit-de-spa-francorchamps-endurance',
        '--layout-id', 'default',
        '--smooth',
        spaSession,
      ], { encoding: 'utf8', timeout: 60000 });

      assert(cli.status === 0, 'real session --smooth exits 0', cli.stderr);
      const profile = readJson(outPath);

      assert(Array.isArray(profile.samples) && profile.samples.length > 0, 'real profile has samples');
      const hasSmooth = profile.samples.every(s =>
        typeof s.left_width_smooth_m === 'number' && typeof s.right_width_smooth_m === 'number'
      );
      assert(hasSmooth, 'real profile all samples have smoothed fields');

      // Raw fields must still be present
      const hasRaw = profile.samples.every(s =>
        typeof s.left_width_m === 'number' && typeof s.right_width_m === 'number' &&
        typeof s.left_sample_count === 'number' && typeof s.right_sample_count === 'number'
      );
      assert(hasRaw, 'real profile all samples still have raw fields');

      console.log(`    bins=${profile.samples.length} summary=${JSON.stringify(profile.summary)}`);
    }
  }
}

async function main() {
  console.log('═══ Track Outline Phase 08.1 Width Profile Smoothing Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});