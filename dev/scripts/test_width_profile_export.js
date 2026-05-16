/**
 * Track outline/apex Phase 07 width profile CLI walking skeleton tests.
 *
 * Run: node scripts/test_width_profile_export.js
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
  const { exportWidthProfile } = require(EXPORT_SCRIPT);

  // ── Queue all Parquet fixtures and create in one batch ──
  const b = new ParquetFixtureBuilder();

  const wpSingle    = b.add('wp-single',    WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0.4, path_lateral_m: -1, track_edge_m: 7.0 },
    { raw_lap_distance_m: 0.8, path_lateral_m: 2,  track_edge_m: 6.0 },
    { raw_lap_distance_m: 1.2, path_lateral_m: -3, track_edge_m: 8.0 },
    { raw_lap_distance_m: 1.6, path_lateral_m: 1,  track_edge_m: 5.0 },
  ]);
  const wpAccA      = b.add('wp-acc-a',     WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0.3, path_lateral_m: -2, track_edge_m: 5.0 },
    { raw_lap_distance_m: 0.7, path_lateral_m: 3,  track_edge_m: 4.0 },
  ]);
  const wpAccB      = b.add('wp-acc-b',     WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0.5, path_lateral_m: -1, track_edge_m: 7.0 },
    { raw_lap_distance_m: 0.6, path_lateral_m: 2,  track_edge_m: 3.0 },
  ]);
  const wpSkip      = b.add('wp-skip',      WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0.5,  path_lateral_m: -1, track_edge_m: 6.0 },
    { raw_lap_distance_m: null,  path_lateral_m: -1, track_edge_m: 5.0 },
    { raw_lap_distance_m: 1.5,   path_lateral_m: null, track_edge_m: 5.0 },
    { raw_lap_distance_m: 2.5,   path_lateral_m: 1,    track_edge_m: null },
    { raw_lap_distance_m: 3.5,   path_lateral_m: -1,   track_edge_m: 0.0 },
  ]);
  const wpOverwrite = b.add('wp-overwrite', WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0, path_lateral_m: -1, track_edge_m: 5 },
  ]);
  const wpCli       = b.add('wp-cli',       WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0, path_lateral_m: -1, track_edge_m: 9 },
    { raw_lap_distance_m: 0, path_lateral_m: 2,  track_edge_m: 6 },
  ]);
  const wpBinkey    = b.add('wp-binkey',    WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0.4, path_lateral_m: -1, track_edge_m: 3.0 },
    { raw_lap_distance_m: 1.9, path_lateral_m: 1,  track_edge_m: 4.0 },
  ]);
  const wpMaxAcc    = b.add('wp-max-acc',   WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0.1, path_lateral_m: -1, track_edge_m: 3.0 },
    { raw_lap_distance_m: 0.2, path_lateral_m: -1, track_edge_m: 5.0 },
    { raw_lap_distance_m: 0.3, path_lateral_m: 1,  track_edge_m: 4.0 },
    { raw_lap_distance_m: 0.4, path_lateral_m: 1,  track_edge_m: 7.0 },
  ]);
  const wpZeroLat   = b.add('wp-zero-lat',  WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0, path_lateral_m: 0, track_edge_m: 5.0 },
  ]);

  b.flush(); // ← single Python process creates all 9 Parquet files at once

  // ── Test 1: Single fixture with left/right binning ──
  console.log('\n── Single fixture: left/right binning ──');
  {
    const outPath = tempPath('wp-single-out', '.json');
    const profile = await exportWidthProfile({
      sessionPaths: [wpSingle],
      trackId: 'test-track',
      layoutId: 'default',
      outPath,
    });

    assert(profile.track_id === 'test-track', 'profile includes track_id', profile.track_id);
    assert(profile.layout_id === 'default', 'profile includes layout_id', profile.layout_id);
    assert(profile.bin_size_m === 1, 'profile includes bin_size_m', String(profile.bin_size_m));

    const samples = profile.samples;
    assert(samples.length === 2, 'profile has 2 bins', String(samples.length));

    const bin0 = samples.find(s => s.s_m === 0);
    const bin1 = samples.find(s => s.s_m === 1);
    assert(bin0, 'bin 0 exists');
    assert(bin1, 'bin 1 exists');

    assert(bin0.left_width_m === 7.0, 'bin 0 left_width_m = 7.0', String(bin0.left_width_m));
    assert(bin0.right_width_m === 6.0, 'bin 0 right_width_m = 6.0', String(bin0.right_width_m));
    assert(bin0.left_sample_count === 1, 'bin 0 left_sample_count = 1', String(bin0.left_sample_count));
    assert(bin0.right_sample_count === 1, 'bin 0 right_sample_count = 1', String(bin0.right_sample_count));

    assert(bin1.left_width_m === 8.0, 'bin 1 left_width_m = 8.0', String(bin1.left_width_m));
    assert(bin1.right_width_m === 5.0, 'bin 1 right_width_m = 5.0', String(bin1.right_width_m));
    assert(bin1.left_sample_count === 1, 'bin 1 left_sample_count = 1', String(bin1.left_sample_count));
    assert(bin1.right_sample_count === 1, 'bin 1 right_sample_count = 1', String(bin1.right_sample_count));

    assert(profile.summary.input_rows === 4, 'summary input_rows = 4', String(profile.summary.input_rows));
    assert(profile.summary.skipped_rows === 0, 'summary skipped_rows = 0', String(profile.summary.skipped_rows));

    // Disk matches returned value
    const disk = readJson(outPath);
    assert(disk.track_id === profile.track_id, 'disk profile matches returned track_id');
    assert(disk.samples.length === 2, 'disk profile has 2 bins');
  }

  // ── Test 2: Multiple sessions accumulate max widths and sample counts ──
  console.log('\n── Multiple sessions: accumulation ──');
  {
    const profile = await exportWidthProfile({
      sessionPaths: [wpAccA, wpAccB],
      trackId: 'acc-track',
      layoutId: 'alt',
      outPath: tempPath('wp-acc-out', '.json'),
    });

    const bin0 = profile.samples.find(s => s.s_m === 0);
    assert(bin0, 'accumulation bin 0 exists');
    assert(bin0.left_width_m === 7.0, 'accumulated left max = 7.0', String(bin0.left_width_m));
    assert(bin0.right_width_m === 4.0, 'accumulated right max = 4.0', String(bin0.right_width_m));
    assert(bin0.left_sample_count === 2, 'accumulated left_sample_count = 2', String(bin0.left_sample_count));
    assert(bin0.right_sample_count === 2, 'accumulated right_sample_count = 2', String(bin0.right_sample_count));
    assert(profile.summary.input_rows === 4, 'accumulation summary input_rows = 4');
    assert(profile.summary.skipped_rows === 0, 'accumulation summary skipped_rows = 0');
  }

  // ── Test 3: Rows missing required fields are skipped and counted ──
  console.log('\n── Missing/non-finite required fields: skip and count ──');
  {
    const profile = await exportWidthProfile({
      sessionPaths: [wpSkip],
      trackId: 'skip-track',
      layoutId: 'default',
      outPath: tempPath('wp-skip-out', '.json'),
    });

    assert(profile.summary.input_rows === 5, 'skip summary input_rows = 5', String(profile.summary.input_rows));
    assert(profile.summary.skipped_rows === 3, 'skip summary skipped_rows = 3', String(profile.summary.skipped_rows));

    const bin0 = profile.samples.find(s => s.s_m === 0);
    const bin3 = profile.samples.find(s => s.s_m === 3);
    assert(bin0 && bin0.left_width_m === 6.0 && bin0.left_sample_count === 1, 'valid row at s=0 bins correctly');
    assert(bin3 && bin3.left_width_m === 0.0 && bin3.left_sample_count === 1, 'valid row at s=3 bins correctly (edge=0)');
    assert(profile.samples.find(s => s.s_m === 1), 'gap at s=1 filled as missing bin');
    assert(profile.samples.find(s => s.s_m === 2), 'gap at s=2 filled as missing bin');
    const gap1 = profile.samples.find(s => s.s_m === 1);
    const gap2 = profile.samples.find(s => s.s_m === 2);
    assert(gap1.status === 'missing', 'gap bin at s=1 has status=missing');
    assert(gap2.status === 'missing', 'gap bin at s=2 has status=missing');
  }

  // ── Test 4: Overwrite refusal ──
  console.log('\n── Overwrite refusal ──');
  {
    const sentinelPath = tempPath('wp-sentinel', '.json');
    fs.writeFileSync(sentinelPath, 'SENTINEL');

    let refused = false;
    try {
      await exportWidthProfile({
        sessionPaths: [wpOverwrite],
        trackId: 'ow-track',
        layoutId: 'default',
        outPath: sentinelPath,
      });
    } catch (err) {
      refused = err.message.includes('exists');
    }
    assert(refused, 'existing output file is refused by default');
    assert(fs.readFileSync(sentinelPath, 'utf8') === 'SENTINEL', 'refused export does not overwrite sentinel');

    await exportWidthProfile({
      sessionPaths: [wpOverwrite],
      trackId: 'ow-track',
      layoutId: 'default',
      outPath: sentinelPath,
      overwrite: true,
    });
    const disk = readJson(sentinelPath);
    assert(disk.track_id === 'ow-track', 'explicit overwrite replaces existing output');
  }

  // ── Test 5: CLI invocation ──
  console.log('\n── CLI invocation ──');
  {
    const cliOut = tempPath('wp-cli-out', '.json');
    const cli = spawnSync('node', [
      EXPORT_SCRIPT,
      '--out', cliOut,
      '--track-id', 'cli-track',
      '--layout-id', 'default',
      wpCli,
    ], { encoding: 'utf8', timeout: 30000 });

    assert(cli.status === 0, 'CLI exits 0', `${cli.stderr}`);
    const disk = readJson(cliOut);
    assert(disk.track_id === 'cli-track', 'CLI output includes track_id', disk.track_id);
    assert(disk.bin_size_m === 1, 'CLI output includes bin_size_m', String(disk.bin_size_m));

    const bin0 = disk.samples.find(s => s.s_m === 0);
    assert(bin0 && bin0.left_width_m === 9, 'CLI bin 0 left_width_m = 9', String(bin0?.left_width_m));
    assert(bin0 && bin0.right_width_m === 6, 'CLI bin 0 right_width_m = 6', String(bin0?.right_width_m));
  }

  // ── Test 6: bin_size_m=1 bucketing via floor ──
  console.log('\n── Bin key floor rule ──');
  {
    const profile = await exportWidthProfile({
      sessionPaths: [wpBinkey],
      trackId: 'binkey-track',
      layoutId: 'default',
      outPath: tempPath('wp-binkey-out', '.json'),
    });

    assert(profile.samples.length === 2, 'binkey produces 2 bins');
    const bin0 = profile.samples.find(s => s.s_m === 0);
    const bin1 = profile.samples.find(s => s.s_m === 1);
    assert(bin0 && bin0.left_width_m === 3.0, 'floor rule: s=0.4 → bin key 0');
    assert(bin1 && bin1.right_width_m === 4.0, 'floor rule: s=1.9 → bin key 1');
  }

  // ── Test 7: same-bin max accumulation within one session ──
  console.log('\n── Same bin max accumulation within one session ──');
  {
    const profile = await exportWidthProfile({
      sessionPaths: [wpMaxAcc],
      trackId: 'max-track',
      layoutId: 'default',
      outPath: tempPath('wp-max-acc-out', '.json'),
    });

    const bin0 = profile.samples.find(s => s.s_m === 0);
    assert(bin0, 'max-acc bin 0 exists');
    assert(bin0.left_width_m === 5.0, 'same-bin left max = 5.0', String(bin0.left_width_m));
    assert(bin0.right_width_m === 7.0, 'same-bin right max = 7.0', String(bin0.right_width_m));
    assert(bin0.left_sample_count === 2, 'same-bin left_sample_count = 2', String(bin0.left_sample_count));
    assert(bin0.right_sample_count === 2, 'same-bin right_sample_count = 2', String(bin0.right_sample_count));
  }

  // ── Test 8: path_lateral_m = 0 goes to right bin ──
  console.log('\n── Zero lateral → right bin ──');
  {
    const profile = await exportWidthProfile({
      sessionPaths: [wpZeroLat],
      trackId: 'zero-lat-track',
      layoutId: 'default',
      outPath: tempPath('wp-zero-lat-out', '.json'),
    });

    const bin0 = profile.samples.find(s => s.s_m === 0);
    assert(bin0, 'zero-lateral bin 0 exists');
    assert(bin0.left_width_m === 0, 'zero-lateral left unchanged (0)', String(bin0.left_width_m));
    assert(bin0.left_sample_count === 0, 'zero-lateral left_sample_count = 0', String(bin0.left_sample_count));
    assert(bin0.right_width_m === 5.0, 'zero-lateral right_width_m = 5.0', String(bin0.right_width_m));
    assert(bin0.right_sample_count === 1, 'zero-lateral right_sample_count = 1', String(bin0.right_sample_count));
  }

  // ── Test 9: Real session integration (Spa endurance) ──
  console.log('\n── Real session: Spa endurance profile ──');
  {
    const spaSession = path.join(ROOT, 'dev', 'sessions', 'session_20260514T182139Z_circuit-de-spa-francorchamps-endurance_lmu.parquet');
    if (!fs.existsSync(spaSession)) {
      console.log('  [SKIP] Spa endurance session not found — skipping real-data test');
    } else {
      const spaOutPath = tempPath('wp-spa-out', '.json');
      const profile = await exportWidthProfile({
        sessionPaths: [spaSession],
        trackId: 'circuit-de-spa-francorchamps-endurance',
        layoutId: 'default',
        outPath: spaOutPath,
      });

      assert(profile.track_id === 'circuit-de-spa-francorchamps-endurance', 'real profile track_id', profile.track_id);
      assert(profile.layout_id === 'default', 'real profile layout_id', profile.layout_id);
      assert(profile.bin_size_m === 1, 'real profile bin_size_m = 1');
      assert(Array.isArray(profile.samples) && profile.samples.length > 0, 'real profile has samples', String(profile.samples.length));
      assert(typeof profile.summary.input_rows === 'number' && profile.summary.input_rows > 0, 'real profile input_rows > 0', String(profile.summary.input_rows));
      assert(typeof profile.summary.skipped_rows === 'number', 'real profile skipped_rows is numeric', String(profile.summary.skipped_rows));

      const badSamples = profile.samples.filter(s =>
        typeof s.s_m !== 'number' ||
        typeof s.left_width_m !== 'number' ||
        typeof s.right_width_m !== 'number' ||
        typeof s.left_sample_count !== 'number' ||
        typeof s.right_sample_count !== 'number'
      );
      assert(badSamples.length === 0, 'real profile samples match §0.4 shape', `${badSamples.length} bad`);

      const rightBins = profile.samples.filter(s => s.right_sample_count > 0 && s.right_width_m > 0);
      assert(rightBins.length > 0, 'real profile has bins with right-width data', String(rightBins.length));

      // Disk round-trip
      const disk = readJson(spaOutPath);
      assert(disk.samples.length === profile.samples.length, 'real profile disk round-trip matches sample count');

      console.log(`    bins=${profile.samples.length} input_rows=${profile.summary.input_rows} skipped=${profile.summary.skipped_rows}`);
    }
  }
}

async function main() {
  console.log('═══ Track Outline Phase 07 Width Profile CLI Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});