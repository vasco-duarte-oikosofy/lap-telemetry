/**
 * Track outline Phase 09 center/path polyline CLI tests.
 *
 * Run: node scripts/test_center_path_export.js
 */
// @parallel true

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..', '..');
const EXPORT_SCRIPT = path.join(ROOT, 'dev/scripts/export_center_path.js');

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

/**
 * Build a synthetic Parquet file with position + lap distance channels.
 * rows: array of { raw_lap_distance_m, pos_x_m, pos_z_m }
 * If a row property is undefined, the column value is null.
 */
function buildParquet(name, rows) {
  const out = tempPath(name, '.parquet');
  function pyList(arr) {
    const inner = arr.map(v => v === null || v === undefined ? 'None' : JSON.stringify(v)).join(', ');
    return `[${inner}]`;
  }
  const rawLapDist = rows.map(r => r.raw_lap_distance_m ?? null);
  const posX = rows.map(r => r.pos_x_m ?? null);
  const posY = rows.map(r => 0);
  const posZ = rows.map(r => r.pos_z_m ?? null);
  const lapNumber = rows.map(() => 1);
  const lapTimeS = rows.map((_, i) => i * 0.1);

  const code = `
import pyarrow as pa, pyarrow.parquet as pq
cols = [
  pa.array(${pyList(lapNumber)}, type=pa.int32()),
  pa.array(${pyList(lapTimeS)}, type=pa.float32()),
  pa.array(${pyList(rawLapDist)}, type=pa.float32()),
  pa.array(${pyList(posX)}, type=pa.float32()),
  pa.array(${pyList(posY)}, type=pa.float32()),
  pa.array(${pyList(posZ)}, type=pa.float32()),
]
names = ['lap_number', 'lap_time_s', 'raw_lap_distance_m',
         'pos_x_m', 'pos_y_m', 'pos_z_m']
pq.write_table(pa.Table.from_arrays(cols, names=names), r'''${out}''', compression='snappy')
`;
  const res = spawnSync('python3', ['-c', code], { encoding: 'utf8', timeout: 30000 });
  if (res.error || res.status !== 0) throw new Error(res.error?.message || res.stderr);
  return out;
}

async function runTests() {
  const { exportCenterPath, buildPathFromRows } = require(EXPORT_SCRIPT);

  // ── Test 1: Single fixture with known positions averaged by bin ──
  console.log('\n── Single fixture: averaged positions per bin ──');
  {
    const session = buildParquet('cp-single', [
      { raw_lap_distance_m: 0.3, pos_x_m: 10.0, pos_z_m: 20.0 },
      { raw_lap_distance_m: 0.7, pos_x_m: 14.0, pos_z_m: 26.0 },
      { raw_lap_distance_m: 1.2, pos_x_m: 30.0, pos_z_m: 40.0 },
    ]);
    const outPath = tempPath('cp-single-out', '.json');

    const result = await exportCenterPath({
      sessionPaths: [session],
      trackId: 'test-track',
      layoutId: 'default',
      outPath,
    });

    assert(result.track_id === 'test-track', 'result includes track_id', result.track_id);
    assert(result.layout_id === 'default', 'result includes layout_id', result.layout_id);
    assert(result.bin_size_m === 1, 'result includes bin_size_m', String(result.bin_size_m));
    assert(Array.isArray(result.points), 'result has points array');
    assert(result.points.length === 2, '2 bins with data', String(result.points.length));

    const p0 = result.points.find(p => p.s_m === 0);
    const p1 = result.points.find(p => p.s_m === 1);
    assert(p0, 'point at s_m=0 exists');
    assert(p1, 'point at s_m=1 exists');

    // Bin 0: average of (10,20) and (14,26) → (12, 23)
    assert(p0.x_m === 12.0, 'bin 0 x_m averaged = 12.0', String(p0.x_m));
    assert(p0.z_m === 23.0, 'bin 0 z_m averaged = 23.0', String(p0.z_m));
    assert(p0.sample_count === 2, 'bin 0 sample_count = 2', String(p0.sample_count));

    // Bin 1: single sample (30, 40)
    assert(p1.x_m === 30.0, 'bin 1 x_m = 30.0', String(p1.x_m));
    assert(p1.z_m === 40.0, 'bin 1 z_m = 40.0', String(p1.z_m));
    assert(p1.sample_count === 1, 'bin 1 sample_count = 1', String(p1.sample_count));

    // Summary
    assert(result.summary.input_rows === 3, 'summary input_rows = 3', String(result.summary.input_rows));
    assert(result.summary.skipped_rows === 0, 'summary skipped_rows = 0', String(result.summary.skipped_rows));

    // Disk round-trip
    const disk = readJson(outPath);
    assert(disk.track_id === result.track_id, 'disk matches returned track_id');
    assert(disk.points.length === 2, 'disk points match count');
  }

  // ── Test 2: Multiple samples in same bin averaged correctly ──
  console.log('\n── Same-bin averaging ──');
  {
    const session = buildParquet('cp-avg', [
      { raw_lap_distance_m: 0.1, pos_x_m: 0.0, pos_z_m: 0.0 },
      { raw_lap_distance_m: 0.2, pos_x_m: 3.0, pos_z_m: 6.0 },
      { raw_lap_distance_m: 0.3, pos_x_m: 6.0, pos_z_m: 12.0 },
      { raw_lap_distance_m: 0.9, pos_x_m: 9.0, pos_z_m: 18.0 },
    ]);
    const outPath = tempPath('cp-avg-out', '.json');

    const result = await exportCenterPath({
      sessionPaths: [session],
      trackId: 'avg-track',
      layoutId: 'default',
      outPath,
    });

    const p0 = result.points.find(p => p.s_m === 0);
    assert(p0, 'avg bin 0 exists');
    assert(p0.sample_count === 4, 'avg bin 0 sample_count = 4', String(p0.sample_count));
    assert(p0.x_m === 4.5, 'avg bin 0 x_m = 4.5', String(p0.x_m));
    assert(p0.z_m === 9.0, 'avg bin 0 z_m = 9.0', String(p0.z_m));
  }

  // ── Test 3: Multiple input sessions accumulate ──
  console.log('\n── Multiple sessions: accumulation ──');
  {
    const sessionA = buildParquet('cp-acc-a', [
      { raw_lap_distance_m: 0.5, pos_x_m: 10.0, pos_z_m: 100.0 },
    ]);
    const sessionB = buildParquet('cp-acc-b', [
      { raw_lap_distance_m: 0.5, pos_x_m: 20.0, pos_z_m: 200.0 },
    ]);
    const outPath = tempPath('cp-acc-out', '.json');

    const result = await exportCenterPath({
      sessionPaths: [sessionA, sessionB],
      trackId: 'acc-track',
      layoutId: 'default',
      outPath,
    });

    const p0 = result.points.find(p => p.s_m === 0);
    assert(p0, 'acc bin 0 exists');
    assert(p0.sample_count === 2, 'acc bin 0 sample_count = 2', String(p0.sample_count));
    assert(p0.x_m === 15.0, 'acc bin 0 x_m averaged = 15.0', String(p0.x_m));
    assert(p0.z_m === 150.0, 'acc bin 0 z_m averaged = 150.0', String(p0.z_m));
    assert(result.summary.input_rows === 2, 'acc summary input_rows = 2');
  }

  // ── Test 4: Rows with missing position fields are skipped and counted ──
  console.log('\n── Missing/non-finite positions: skip and count ──');
  {
    const session = buildParquet('cp-skip', [
      { raw_lap_distance_m: 0.5, pos_x_m: 10.0, pos_z_m: 20.0 },     // valid
      { raw_lap_distance_m: 1.5, pos_x_m: null, pos_z_m: 30.0 },     // missing pos_x_m
      { raw_lap_distance_m: 2.5, pos_x_m: 50.0, pos_z_m: null },     // missing pos_z_m
      { raw_lap_distance_m: 3.5, pos_x_m: 70.0, pos_z_m: 80.0 },     // valid
      { raw_lap_distance_m: 4.5, pos_x_m: null, pos_z_m: null },     // both missing
    ]);
    const outPath = tempPath('cp-skip-out', '.json');

    const result = await exportCenterPath({
      sessionPaths: [session],
      trackId: 'skip-track',
      layoutId: 'default',
      outPath,
    });

    assert(result.summary.input_rows === 5, 'skip summary input_rows = 5', String(result.summary.input_rows));
    assert(result.summary.skipped_rows === 3, 'skip summary skipped_rows = 3', String(result.summary.skipped_rows));
    assert(result.points.length === 2, 'skip result has 2 valid bins', String(result.points.length));

    const p0 = result.points.find(p => p.s_m === 0);
    const p3 = result.points.find(p => p.s_m === 3);
    assert(p0 && p0.x_m === 10.0 && p0.z_m === 20.0, 'valid row at s=0 bins correctly');
    assert(p3 && p3.x_m === 70.0 && p3.z_m === 80.0, 'valid row at s=3 bins correctly');
  }

  // ── Test 5: Points ordered by increasing s_m ──
  console.log('\n── Points ordered by increasing s_m ──');
  {
    const session = buildParquet('cp-order', [
      { raw_lap_distance_m: 5.2, pos_x_m: 50.0, pos_z_m: 50.0 },
      { raw_lap_distance_m: 1.1, pos_x_m: 10.0, pos_z_m: 10.0 },
      { raw_lap_distance_m: 3.3, pos_x_m: 30.0, pos_z_m: 30.0 },
    ]);
    const outPath = tempPath('cp-order-out', '.json');

    const result = await exportCenterPath({
      sessionPaths: [session],
      trackId: 'order-track',
      layoutId: 'default',
      outPath,
    });

    assert(result.points.length === 3, 'order result has 3 points');
    const sValues = result.points.map(p => p.s_m);
    for (let i = 1; i < sValues.length; i++) {
      assert(sValues[i] > sValues[i - 1], `s_m ascending at index ${i}`, `${sValues[i - 1]} < ${sValues[i]}`);
    }
  }

  // ── Test 6: No gap-filling — missing bins absent ──
  console.log('\n── No gap-filling: missing bins absent ──');
  {
    const session = buildParquet('cp-gap', [
      { raw_lap_distance_m: 0.5, pos_x_m: 1.0, pos_z_m: 1.0 },
      { raw_lap_distance_m: 5.5, pos_x_m: 5.0, pos_z_m: 5.0 },
    ]);
    const outPath = tempPath('cp-gap-out', '.json');

    const result = await exportCenterPath({
      sessionPaths: [session],
      trackId: 'gap-track',
      layoutId: 'default',
      outPath,
    });

    assert(result.points.length === 2, 'gap result has exactly 2 points', String(result.points.length));
    assert(result.points[0].s_m === 0, 'first point at s_m=0', String(result.points[0].s_m));
    assert(result.points[1].s_m === 5, 'second point at s_m=5', String(result.points[1].s_m));
    assert(!result.points.find(p => p.s_m === 1), 's_m=1 absent (gap)');
    assert(!result.points.find(p => p.s_m === 2), 's_m=2 absent (gap)');
    assert(!result.points.find(p => p.s_m === 3), 's_m=3 absent (gap)');
    assert(!result.points.find(p => p.s_m === 4), 's_m=4 absent (gap)');
  }

  // ── Test 7: buildPathFromRows pure function ──
  console.log('\n── buildPathFromRows pure function ──');
  {
    const rows = [
      { raw_lap_distance_m: 0.3, pos_x_m: 2.0, pos_z_m: 4.0 },
      { raw_lap_distance_m: 0.7, pos_x_m: 6.0, pos_z_m: 8.0 },
      { raw_lap_distance_m: 2.1, pos_x_m: 20.0, pos_z_m: 40.0 },
    ];
    const { points, skipped } = buildPathFromRows(rows, 1);

    assert(points.length === 2, 'pure function: 2 bins', String(points.length));
    assert(skipped === 0, 'pure function: 0 skipped', String(skipped));

    const p0 = points.find(p => p.s_m === 0);
    assert(p0 && p0.x_m === 4.0, 'pure function: bin 0 x_m = 4.0', String(p0?.x_m));
    assert(p0 && p0.z_m === 6.0, 'pure function: bin 0 z_m = 6.0', String(p0?.z_m));
    assert(p0 && p0.sample_count === 2, 'pure function: bin 0 sample_count = 2', String(p0?.sample_count));
  }

  // ── Test 8: CLI invocation ──
  console.log('\n── CLI invocation ──');
  {
    const session = buildParquet('cp-cli', [
      { raw_lap_distance_m: 0, pos_x_m: -136.94, pos_z_m: 646.23 },
      { raw_lap_distance_m: 0, pos_x_m: -137.06, pos_z_m: 646.17 },
    ]);
    const cliOut = tempPath('cp-cli-out', '.json');
    const cli = spawnSync('node', [
      EXPORT_SCRIPT,
      '--out', cliOut,
      '--track-id', 'cli-track',
      '--layout-id', 'default',
      session,
    ], { encoding: 'utf8', timeout: 30000 });

    assert(cli.status === 0, 'CLI exits 0', `${cli.stderr}`);
    const disk = readJson(cliOut);
    assert(disk.track_id === 'cli-track', 'CLI output includes track_id', disk.track_id);
    assert(disk.bin_size_m === 1, 'CLI output includes bin_size_m', String(disk.bin_size_m));
    assert(Array.isArray(disk.points), 'CLI output has points array');
    assert(disk.points.length === 1, 'CLI output has 1 point', String(disk.points.length));

    const p0 = disk.points[0];
    assert(p0.s_m === 0, 'CLI point at s_m=0', String(p0.s_m));
    assert(p0.sample_count === 2, 'CLI point sample_count = 2', String(p0.sample_count));
    // Averaged: (-136.94 + -137.06)/2 = -137.0, (646.23 + 646.17)/2 = 646.2
    assert(p0.x_m === -137.0, 'CLI point x_m = -137.0', String(p0.x_m));
    assert(Math.abs(p0.z_m - 646.2) < 0.01, 'CLI point z_m ≈ 646.2', String(p0.z_m));
    assert(disk.summary.input_rows === 2, 'CLI summary input_rows = 2');
    assert(disk.summary.skipped_rows === 0, 'CLI summary skipped_rows = 0');
  }

  // ── Test 9: Overwrite refusal ──
  console.log('\n── Overwrite refusal ──');
  {
    const session = buildParquet('cp-ow', [
      { raw_lap_distance_m: 0, pos_x_m: 0, pos_z_m: 0 },
    ]);
    const sentinelPath = tempPath('cp-sentinel', '.json');
    fs.writeFileSync(sentinelPath, 'SENTINEL');

    let refused = false;
    try {
      await exportCenterPath({
        sessionPaths: [session],
        trackId: 'ow-track',
        layoutId: 'default',
        outPath: sentinelPath,
      });
    } catch (err) {
      refused = err.message.includes('exists');
    }
    assert(refused, 'existing output file is refused by default');

    await exportCenterPath({
      sessionPaths: [session],
      trackId: 'ow-track',
      layoutId: 'default',
      outPath: sentinelPath,
      overwrite: true,
    });
    const disk = readJson(sentinelPath);
    assert(disk.track_id === 'ow-track', 'explicit overwrite replaces existing output');
  }

  // ── Test 10: Real session integration (Spa endurance) ──
  console.log('\n── Real session: Spa endurance center path ──');
  {
    const spaSession = path.join(ROOT, 'dev', 'sessions', 'session_20260514T182139Z_circuit-de-spa-francorchamps-endurance_lmu.parquet');
    if (!fs.existsSync(spaSession)) {
      console.log('  [SKIP] Spa endurance session not found — skipping real-data test');
    } else {
      const outPath = tempPath('cp-spa-out', '.json');
      const result = await exportCenterPath({
        sessionPaths: [spaSession],
        trackId: 'circuit-de-spa-francorchamps-endurance',
        layoutId: 'default',
        outPath,
      });

      assert(result.track_id === 'circuit-de-spa-francorchamps-endurance', 'real track_id', result.track_id);
      assert(result.layout_id === 'default', 'real layout_id', result.layout_id);
      assert(result.bin_size_m === 1, 'real bin_size_m = 1');
      assert(Array.isArray(result.points) && result.points.length > 0, 'real has points', String(result.points.length));
      assert(typeof result.summary.input_rows === 'number' && result.summary.input_rows > 0, 'real input_rows > 0', String(result.summary.input_rows));
      assert(typeof result.summary.skipped_rows === 'number', 'real skipped_rows is numeric', String(result.summary.skipped_rows));

      // All points should have required shape
      const badPoints = result.points.filter(p =>
        typeof p.s_m !== 'number' ||
        typeof p.x_m !== 'number' ||
        typeof p.z_m !== 'number' ||
        typeof p.sample_count !== 'number'
      );
      assert(badPoints.length === 0, 'real points match expected shape', `${badPoints.length} bad`);

      // Points should be sorted by s_m
      const sValues = result.points.map(p => p.s_m);
      let sorted = true;
      for (let i = 1; i < sValues.length; i++) {
        if (sValues[i] <= sValues[i - 1]) { sorted = false; break; }
      }
      assert(sorted, 'real points sorted by s_m');

      // Disk round-trip
      const disk = readJson(outPath);
      assert(disk.points.length === result.points.length, 'real disk round-trip matches point count');

      console.log(`    points=${result.points.length} input_rows=${result.summary.input_rows} skipped=${result.summary.skipped_rows}`);
    }
  }

  // ── Test 11: Existing width-profile command unchanged ──
  console.log('\n── Width profile command still works ──');
  {
    const wpScript = path.join(ROOT, 'dev/scripts/export_width_profile.js');
    const session = buildParquet('cp-wp', [
      { raw_lap_distance_m: 0.5, path_lateral_m: -1, track_edge_m: 6.0 },
    ]);
    const wpOut = tempPath('cp-wp-out', '.json');
    const wp = spawnSync('node', [
      wpScript,
      '--out', wpOut,
      '--track-id', 'cp-wp-track',
      '--layout-id', 'default',
      session,
    ], { encoding: 'utf8', timeout: 30000 });

    assert(wp.status === 0, 'width profile CLI still exits 0', `${wp.stderr}`);
    const disk = readJson(wpOut);
    assert(disk.track_id === 'cp-wp-track', 'width profile still produces valid output');
    assert(Array.isArray(disk.samples), 'width profile still has samples array');
  }
}

async function main() {
  console.log('═══ Track Outline Phase 09 Center/Path Polyline CLI Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});