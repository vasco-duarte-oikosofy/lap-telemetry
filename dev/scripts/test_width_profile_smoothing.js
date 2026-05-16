/**
 * Track outline Phase 08.1 — Width profile interpolation and smoothing tests.
 *
 * Run: node scripts/test_width_profile_smoothing.js
 */
// @parallel true

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const { ParquetFixtureBuilder, WIDTH_PROFILE_COLS } = require('./parquet-fixture');

const ROOT = path.resolve(__dirname, '..', '..');
const EXPORT_SCRIPT = path.join(ROOT, 'dev/scripts/export_width_profile.js');

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

async function runTests() {
  const { exportWidthProfile, buildProfileFromRows, interpolateAndSmooth } = require(EXPORT_SCRIPT);

  // ── Queue all Parquet fixtures and create in one batch ──
  const b = new ParquetFixtureBuilder();

  // Test 6: CLI --smooth
  const wpSmoothCli = b.add('wp-smooth-cli', WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0.1, path_lateral_m: -1, track_edge_m: 8 },
    { raw_lap_distance_m: 0.2, path_lateral_m: 1,  track_edge_m: 6 },
    { raw_lap_distance_m: 0.3, path_lateral_m: -1, track_edge_m: 8 },
    { raw_lap_distance_m: 0.4, path_lateral_m: 1,  track_edge_m: 6 },
    { raw_lap_distance_m: 0.5, path_lateral_m: -1, track_edge_m: 8 },
    { raw_lap_distance_m: 0.6, path_lateral_m: 1,  track_edge_m: 6 },
    { raw_lap_distance_m: 0.7, path_lateral_m: -1, track_edge_m: 8 },
    { raw_lap_distance_m: 0.8, path_lateral_m: 1,  track_edge_m: 6 },
    { raw_lap_distance_m: 5.1, path_lateral_m: -1, track_edge_m: 10 },
    { raw_lap_distance_m: 5.2, path_lateral_m: 1,  track_edge_m: 8 },
    { raw_lap_distance_m: 5.3, path_lateral_m: -1, track_edge_m: 10 },
    { raw_lap_distance_m: 5.4, path_lateral_m: 1,  track_edge_m: 8 },
    { raw_lap_distance_m: 5.5, path_lateral_m: -1, track_edge_m: 10 },
    { raw_lap_distance_m: 5.6, path_lateral_m: 1,  track_edge_m: 8 },
    { raw_lap_distance_m: 5.7, path_lateral_m: -1, track_edge_m: 10 },
    { raw_lap_distance_m: 5.8, path_lateral_m: 1,  track_edge_m: 8 },
  ]);

  // Test 7: CLI without --smooth
  const wpRawCli = b.add('wp-raw-cli', WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0.1, path_lateral_m: -1, track_edge_m: 8 },
    { raw_lap_distance_m: 0.2, path_lateral_m: 1,  track_edge_m: 6 },
  ]);

  b.flush(); // ← single Python process creates both Parquet files at once

  // ── Test 1: Short gap (3 bins) linearly interpolated ──
  console.log('\n── Short gap linear interpolation ──');
  {
    const rows = [
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 8 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 5), path_lateral_m: 1, track_edge_m: 6 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 4.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 12 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 4.1 + 0.1 * (i + 4), path_lateral_m: 1, track_edge_m: 10 })),
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const smoothed = interpolateAndSmooth(samples);

    const s1 = smoothed.find(s => s.s_m === 1);
    const s2 = smoothed.find(s => s.s_m === 2);
    const s3 = smoothed.find(s => s.s_m === 3);

    assert(s1 && s1.left_width_smooth_m != null, 's=1 has left_width_smooth_m');
    assert(s1 && s1.right_width_smooth_m != null, 's=1 has right_width_smooth_m');

    assert(s2 && Math.abs(s2.left_width_smooth_m - 10) < 0.5,
      's=2 left_width_smooth_m ≈ 10 (interpolated midpoint)', String(s2?.left_width_smooth_m));
    assert(s2 && Math.abs(s2.right_width_smooth_m - 8) < 0.5,
      's=2 right_width_smooth_m ≈ 8 (interpolated midpoint)', String(s2?.right_width_smooth_m));
  }

  // ── Test 2: Long gap NOT interpolated ──
  console.log('\n── Long gap stays missing ──');
  {
    const rows = [
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 8 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 5), path_lateral_m: 1, track_edge_m: 6 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 16.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 12 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 16.1 + 0.1 * (i + 4), path_lateral_m: 1, track_edge_m: 10 })),
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const smoothed = interpolateAndSmooth(samples);

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
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 5 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.05 * (i + 1), path_lateral_m: 1, track_edge_m: 4 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 1.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 10 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 1.05 + 0.05 * i, path_lateral_m: 1, track_edge_m: 9 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 2.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 7 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 2.05 + 0.05 * i, path_lateral_m: 1, track_edge_m: 6 })),
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const smoothed = interpolateAndSmooth(samples);

    for (const bin of smoothed) {
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

    const anyDiff = smoothed.some(s => s.left_width_smooth_m !== s.left_width_m || s.right_width_smooth_m !== s.right_width_m);
    assert(anyDiff, 'smoothing produces different values from raw for at least one bin');
  }

  // ── Test 4: Smoothing narrows adjacent-bin differences ──
  console.log('\n── Smoothing narrows adjacent differences ──');
  {
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
    assert(bin1.left_width_smooth_m < bin1.left_width_m,
      'smoothed spike < raw spike', `${bin1.left_width_smooth_m} < ${bin1.left_width_m}`);
    assert(bin1.right_width_smooth_m < bin1.right_width_m,
      'smoothed right spike < raw', `${bin1.right_width_smooth_m} < ${bin1.right_width_m}`);
  }

  // ── Test 5: No smoothing across long gaps ──
  console.log('\n── No smoothing across long gaps ──');
  {
    const rows = [
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 8 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.05 * (i + 1), path_lateral_m: 1, track_edge_m: 6 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 16.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 12 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 16.05 + 0.05 * i, path_lateral_m: 1, track_edge_m: 10 })),
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const smoothed = interpolateAndSmooth(samples);

    const bin0 = smoothed.find(s => s.s_m === 0);
    const bin16 = smoothed.find(s => s.s_m === 16);
    assert(bin0 && bin0.left_width_smooth_m === bin0.left_width_m,
      'long-gap edge bin: smoothed = raw (only gap neighbors)', String(bin0?.left_width_smooth_m));
    assert(bin16 && bin16.left_width_smooth_m === bin16.left_width_m,
      'long-gap other edge bin: smoothed = raw', String(bin16?.left_width_smooth_m));
  }

  // ── Test 6: CLI --smooth produces smoothed fields ──
  console.log('\n── CLI --smooth flag adds smoothed fields ──');
  {
    const smoothOut = tempPath('wp-smooth-cli-out', '.json');
    const cli = spawnSync('node', [
      EXPORT_SCRIPT,
      '--out', smoothOut,
      '--track-id', 'smooth-track',
      '--layout-id', 'default',
      '--smooth',
      wpSmoothCli,
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
    const rawOut = tempPath('wp-raw-cli-out', '.json');
    const cli = spawnSync('node', [
      EXPORT_SCRIPT,
      '--out', rawOut,
      '--track-id', 'raw-track',
      '--layout-id', 'default',
      wpRawCli,
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

    const s11 = smoothed.find(s => s.s_m === 11);

    assert(s11 && Math.abs(s11.left_width_smooth_m - 14) < 1,
      'gap midpoint left smooth ≈ 14', String(s11?.left_width_smooth_m));
    assert(s11 && Math.abs(s11.right_width_smooth_m - 12) < 1,
      'gap midpoint right smooth ≈ 12', String(s11?.right_width_smooth_m));

    const s2 = smoothed.find(s => s.s_m === 2);
    assert(s2 && Math.abs(s2.left_width_smooth_m - 10) < 0.5,
      'non-gap flat bin left smooth ≈ 10', String(s2?.left_width_smooth_m));
    assert(s2 && Math.abs(s2.right_width_smooth_m - 8) < 0.5,
      'non-gap flat bin right smooth ≈ 8', String(s2?.right_width_smooth_m));
  }

  // ── Test 9: Real session smoke test with --smooth ──
  console.log('\n── Real session smoke: Spa endurance with --smooth ──');
  {
    const spaSession = path.join(ROOT, 'dev', 'sessions', 'session_20260514T182139Z_circuit-de-spa-francorchamps-endurance_lmu.parquet');
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