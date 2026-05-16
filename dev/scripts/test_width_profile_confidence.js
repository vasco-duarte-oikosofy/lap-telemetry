/**
 * Track outline Phase 08 — Width profile confidence and gap flags tests.
 *
 * Run: node scripts/test_width_profile_confidence.js
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
  const { exportWidthProfile, buildProfileFromRows } = require(EXPORT_SCRIPT);

  // ── Queue all Parquet fixtures and create in one batch ──
  const b = new ParquetFixtureBuilder();

  // Test 7 fixtures
  const wpConfCli = b.add('wp-conf-cli', WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0.1, path_lateral_m: -1, track_edge_m: 5 },
    { raw_lap_distance_m: 0.2, path_lateral_m: -1, track_edge_m: 5 },
    { raw_lap_distance_m: 0.3, path_lateral_m: -1, track_edge_m: 5 },
    { raw_lap_distance_m: 0.4, path_lateral_m: 1,  track_edge_m: 4 },
    { raw_lap_distance_m: 0.5, path_lateral_m: 1,  track_edge_m: 4 },
    { raw_lap_distance_m: 0.6, path_lateral_m: 1,  track_edge_m: 4 },
    { raw_lap_distance_m: 3.1, path_lateral_m: 2,  track_edge_m: 6 },
  ]);

  // Test 8 fixtures
  const wpConfStdout = b.add('wp-conf-stdout', WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0.1, path_lateral_m: -1, track_edge_m: 5 },
    { raw_lap_distance_m: 3.1, path_lateral_m: 1,  track_edge_m: 4 },
  ]);

  // Test 10 fixtures (negative track_edge_m)
  const wpNegTe = b.add('wp-neg-te', WIDTH_PROFILE_COLS, [
    { raw_lap_distance_m: 0.5, path_lateral_m: -2, track_edge_m: -7.4 },
    { raw_lap_distance_m: 0.6, path_lateral_m: 1,  track_edge_m: 6.8 },
  ]);

  b.flush(); // ← single Python process creates all 3 Parquet files at once

  // ── Test 1: Complete bins get status="complete" and confidence=1 ──
  console.log('\n── Complete bins: both sides, adequate samples ──');
  {
    const rows = [];
    for (let i = 0; i < 4; i++) {
      rows.push({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 5.0 + i });
      rows.push({ raw_lap_distance_m: 0.2 * (i + 1), path_lateral_m: 1, track_edge_m: 6.0 + i });
    }
    const { samples } = buildProfileFromRows(rows, 1);
    const bin0 = samples.find(s => s.s_m === 0);

    assert(bin0, 'complete bin 0 exists');
    assert(bin0.status === 'complete', 'complete bin status = "complete"', bin0.status);
    assert(bin0.confidence === 1, 'complete bin confidence = 1', String(bin0.confidence));
  }

  // ── Test 2: One-sided bins: only one side has samples ──
  console.log('\n── One-sided bins ──');
  {
    const rows = [];
    for (let i = 0; i < 5; i++) {
      rows.push({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 7.0 });
    }
    for (let i = 0; i < 5; i++) {
      rows.push({ raw_lap_distance_m: 1.1 + 0.1 * i, path_lateral_m: 2, track_edge_m: 6.0 });
    }
    const { samples } = buildProfileFromRows(rows, 1);
    const bin0 = samples.find(s => s.s_m === 0);
    const bin1 = samples.find(s => s.s_m === 1);

    assert(bin0 && bin0.status === 'one-sided', 'left-only bin status = "one-sided"', bin0?.status);
    assert(bin0 && bin0.confidence === 0.5, 'left-only bin confidence = 0.5', String(bin0?.confidence));
    assert(bin1 && bin1.status === 'one-sided', 'right-only bin status = "one-sided"', bin1?.status);
    assert(bin1 && bin1.confidence === 0.5, 'right-only bin confidence = 0.5', String(bin1?.confidence));
  }

  // ── Test 3: Low-sample bins: both sides present but < MIN_SAMPLES on one side ──
  console.log('\n── Low-sample bins ──');
  {
    const rows = [
      { raw_lap_distance_m: 0.1, path_lateral_m: -1, track_edge_m: 5 },
      { raw_lap_distance_m: 0.2, path_lateral_m: -1, track_edge_m: 5 },
      { raw_lap_distance_m: 0.3, path_lateral_m: -1, track_edge_m: 5 },
      { raw_lap_distance_m: 0.4, path_lateral_m: -1, track_edge_m: 5 },
      { raw_lap_distance_m: 0.5, path_lateral_m: 1, track_edge_m: 4 },
      { raw_lap_distance_m: 0.6, path_lateral_m: 1, track_edge_m: 4 },
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const bin0 = samples.find(s => s.s_m === 0);

    assert(bin0 && bin0.status === 'low-sample', 'low-sample bin status = "low-sample"', bin0.status);
    assert(bin0 && bin0.confidence === 0.75, 'low-sample bin confidence = 0.75', String(bin0.confidence));
  }

  // ── Test 4: Missing bins (gaps) are explicitly present, not omitted ──
  console.log('\n── Missing gap bins are explicit ──');
  {
    const rows = [
      { raw_lap_distance_m: 0.5, path_lateral_m: -1, track_edge_m: 5 },
      { raw_lap_distance_m: 3.5, path_lateral_m: 1, track_edge_m: 6 },
    ];
    const { samples } = buildProfileFromRows(rows, 1);

    const s0 = samples.find(s => s.s_m === 0);
    const s1 = samples.find(s => s.s_m === 1);
    const s2 = samples.find(s => s.s_m === 2);
    const s3 = samples.find(s => s.s_m === 3);

    assert(samples.length === 4, 'gap-filled profile has 4 bins', String(samples.length));
    assert(s1, 'gap bin at s=1 exists (not omitted)');
    assert(s2, 'gap bin at s=2 exists (not omitted)');
    assert(s1.status === 'missing', 'gap bin s=1 status = "missing"', s1.status);
    assert(s1.confidence === 0, 'gap bin s=1 confidence = 0', String(s1.confidence));
    assert(s2.status === 'missing', 'gap bin s=2 status = "missing"', s2.status);
    assert(s2.confidence === 0, 'gap bin s=2 confidence = 0', String(s2.confidence));
    assert(s1.left_width_m === 0, 'gap bin left_width_m = 0', String(s1.left_width_m));
    assert(s1.right_width_m === 0, 'gap bin right_width_m = 0', String(s1.right_width_m));
    assert(s1.left_sample_count === 0, 'gap bin left_sample_count = 0', String(s1.left_sample_count));
    assert(s1.right_sample_count === 0, 'gap bin right_sample_count = 0', String(s1.right_sample_count));
  }

  // ── Test 5: Negative track_edge_m uses abs for width ──
  console.log('\n── Negative track_edge_m uses abs() ──');
  {
    const rows = [
      { raw_lap_distance_m: 0.5, path_lateral_m: -2, track_edge_m: -7.4 },
      { raw_lap_distance_m: 0.6, path_lateral_m: 1, track_edge_m: 6.8 },
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const bin0 = samples.find(s => s.s_m === 0);

    assert(bin0 && bin0.left_width_m === 7.4, 'abs(track_edge_m) used for left width', String(bin0?.left_width_m));
    assert(bin0 && bin0.right_width_m === 6.8, 'right width unchanged', String(bin0?.right_width_m));
  }

  // ── Test 6: Confidence ordering: complete > low-sample > one-sided > missing ──
  console.log('\n── Confidence ordering ──');
  {
    const rows = [
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 5 })),
      ...Array.from({ length: 3 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 5), path_lateral_m: 1, track_edge_m: 4 })),
      ...Array.from({ length: 3 }, (_, i) => ({ raw_lap_distance_m: 5.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 7 })),
    ];
    const { samples } = buildProfileFromRows(rows, 1);

    const complete = samples.find(s => s.s_m === 0);
    const oneSided = samples.find(s => s.s_m === 5);

    assert(complete.confidence > oneSided.confidence, 'complete.confidence > one-sided.confidence');
    assert(oneSided.confidence > 0, 'one-sided.confidence > 0 (missing)');
  }

  // ── Test 7: CLI summary includes missing, one-sided, low-confidence counts ──
  console.log('\n── CLI summary aggregate counts ──');
  {
    const profile = await exportWidthProfile({
      sessionPaths: [wpConfCli],
      trackId: 'conf-track',
      layoutId: 'default',
      outPath: tempPath('wp-conf-cli-out', '.json'),
    });

    const summary = profile.summary;
    assert(typeof summary.missing_bins === 'number', 'summary includes missing_bins', String(summary.missing_bins));
    assert(typeof summary.one_sided_bins === 'number', 'summary includes one_sided_bins', String(summary.one_sided_bins));
    assert(typeof summary.low_sample_bins === 'number', 'summary includes low_sample_bins', String(summary.low_sample_bins));
    assert(typeof summary.complete_bins === 'number', 'summary includes complete_bins', String(summary.complete_bins));

    assert(summary.complete_bins === 1, 'summary complete_bins = 1', String(summary.complete_bins));
    assert(summary.missing_bins === 2, 'summary missing_bins = 2', String(summary.missing_bins));
    assert(summary.one_sided_bins === 1, 'summary one_sided_bins = 1', String(summary.one_sided_bins));
    assert(summary.low_sample_bins === 0, 'summary low_sample_bins = 0', String(summary.low_sample_bins));

    const totalExplicit = summary.complete_bins + summary.one_sided_bins + summary.low_sample_bins + summary.missing_bins;
    assert(totalExplicit === profile.samples.length, 'status counts sum to total bins', `${totalExplicit} vs ${profile.samples.length}`);
  }

  // ── Test 8: CLI output prints confidence summary ──
  console.log('\n── CLI output prints confidence summary ──');
  {
    const cliOut = tempPath('wp-conf-stdout-out', '.json');
    const cli = spawnSync('node', [
      EXPORT_SCRIPT,
      '--out', cliOut,
      '--track-id', 'stdout-track',
      '--layout-id', 'default',
      wpConfStdout,
    ], { encoding: 'utf8', timeout: 30000 });

    assert(cli.status === 0, 'CLI exits 0', cli.stderr);
    assert(cli.stdout.includes('complete'), 'CLI stdout mentions "complete"');
    assert(cli.stdout.includes('missing'), 'CLI stdout mentions "missing"');
    assert(cli.stdout.includes('one-sided'), 'CLI stdout mentions "one-sided"');
    assert(cli.stdout.includes('low-sample'), 'CLI stdout mentions "low-sample"');
  }

  // ── Test 9: Full profile fixture with all statuses ──
  console.log('\n── Mixed fixture: all four statuses ──');
  {
    const rows = [
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 1), path_lateral_m: -1, track_edge_m: 5 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 0.1 * (i + 5), path_lateral_m: 1, track_edge_m: 4 })),
      ...Array.from({ length: 4 }, (_, i) => ({ raw_lap_distance_m: 1.1 + 0.1 * i, path_lateral_m: -1, track_edge_m: 6 })),
      ...Array.from({ length: 2 }, (_, i) => ({ raw_lap_distance_m: 1.1 + 0.1 * (i + 4), path_lateral_m: 1, track_edge_m: 3 })),
      ...Array.from({ length: 3 }, (_, i) => ({ raw_lap_distance_m: 5.1 + 0.1 * i, path_lateral_m: 2, track_edge_m: 7 })),
    ];
    const { samples, missing_bins, one_sided_bins, low_sample_bins, complete_bins } = buildProfileFromRows(rows, 1);

    assert(samples.length === 6, 'mixed fixture has 6 bins (including 3 gaps)', String(samples.length));

    const bin0 = samples.find(s => s.s_m === 0);
    const bin1 = samples.find(s => s.s_m === 1);
    const bin2 = samples.find(s => s.s_m === 2);
    const bin3 = samples.find(s => s.s_m === 3);
    const bin4 = samples.find(s => s.s_m === 4);
    const bin5 = samples.find(s => s.s_m === 5);

    assert(bin0.status === 'complete' && bin0.confidence === 1, 'bin 0 complete', `${bin0.status}/${bin0.confidence}`);
    assert(bin1.status === 'low-sample' && bin1.confidence === 0.75, 'bin 1 low-sample', `${bin1.status}/${bin1.confidence}`);
    assert(bin2.status === 'missing' && bin2.confidence === 0, 'bin 2 missing', `${bin2.status}/${bin2.confidence}`);
    assert(bin3.status === 'missing' && bin3.confidence === 0, 'bin 3 missing', `${bin3.status}/${bin3.confidence}`);
    assert(bin4.status === 'missing' && bin4.confidence === 0, 'bin 4 missing', `${bin4.status}/${bin4.confidence}`);
    assert(bin5.status === 'one-sided' && bin5.confidence === 0.5, 'bin 5 one-sided', `${bin5.status}/${bin5.confidence}`);

    assert(complete_bins === 1, 'summary complete_bins = 1', String(complete_bins));
    assert(one_sided_bins === 1, 'summary one_sided_bins = 1', String(one_sided_bins));
    assert(low_sample_bins === 1, 'summary low_sample_bins = 1', String(low_sample_bins));
    assert(missing_bins === 3, 'summary missing_bins = 3', String(missing_bins));
  }

  // ── Test 10: Negative track_edge_m with confidence (full flow via Parquet) ──
  console.log('\n── Negative track_edge_m via Parquet round-trip ──');
  {
    const profile = await exportWidthProfile({
      sessionPaths: [wpNegTe],
      trackId: 'neg-te-track',
      layoutId: 'default',
      outPath: tempPath('wp-neg-te-out', '.json'),
    });

    const bin0 = profile.samples.find(s => s.s_m === 0);
    assert(bin0 && Math.abs(bin0.left_width_m - 7.4) < 0.001, 'parquet: abs(track_edge_m) for left width', String(bin0?.left_width_m));
    assert(bin0 && Math.abs(bin0.right_width_m - 6.8) < 0.001, 'parquet: right width correct', String(bin0?.right_width_m));
  }

  // ── Test 11: Low-sample bin with both sides under MIN ──
  console.log('\n── Both sides under MIN_SAMPLES ──');
  {
    const rows = [
      { raw_lap_distance_m: 0.1, path_lateral_m: -1, track_edge_m: 5 },
      { raw_lap_distance_m: 0.2, path_lateral_m: -1, track_edge_m: 5 },
      { raw_lap_distance_m: 0.3, path_lateral_m: 1, track_edge_m: 4 },
      { raw_lap_distance_m: 0.4, path_lateral_m: 1, track_edge_m: 4 },
    ];
    const { samples } = buildProfileFromRows(rows, 1);
    const bin0 = samples.find(s => s.s_m === 0);

    assert(bin0 && bin0.status === 'low-sample', 'both-sides-under-MIN status = "low-sample"', bin0?.status);
    assert(bin0 && bin0.confidence === 0.75, 'both-sides-under-MIN confidence = 0.75', String(bin0?.confidence));
  }
}

async function main() {
  console.log('═══ Track Outline Phase 08 Width Profile Confidence Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});