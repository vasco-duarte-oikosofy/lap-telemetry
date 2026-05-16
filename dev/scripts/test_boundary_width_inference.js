/**
 * Track outline Phase 09.3 — one-sided boundary width inference tests.
 *
 * Run: node scripts/test_boundary_width_inference.js
 */

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

function approxEq(a, b, eps = 1e-6) {
  return Math.abs(a - b) < eps;
}

function tempPath(name, ext) {
  return path.join(os.tmpdir(), `${name}-${Date.now()}-${Math.random().toString(16).slice(2)}${ext}`);
}

function sample(s_m, left, right, status = 'complete', confidence = 1) {
  return { s_m, left_width_m: left, right_width_m: right, status, confidence };
}

async function runTests() {
  const { computeBoundaries, inferMissingWidths } = require(SCRIPT);

  console.log('\n── Short one-sided run infers missing side ──');
  {
    const samples = [
      sample(0, 6, 8), sample(1, 6, 8),
      sample(2, 0, 9, 'one-sided', 0.4), sample(3, 0, 10, 'one-sided', 0.4),
      sample(4, 7, 7), sample(5, 8, 6),
    ];
    const out = inferMissingWidths(samples, { window: 3, maxRun: 3, minCompleteNeighbors: 2 });
    assert(approxEq(out.samples[2].left_width_inferred_m, 5), 's=2 left inferred to median total minus right', String(out.samples[2].left_width_inferred_m));
    assert(approxEq(out.samples[3].left_width_inferred_m, 4), 's=3 left inferred to median total minus right', String(out.samples[3].left_width_inferred_m));
    assert(out.summary.inferred_left_widths === 2, 'summary counts two left inferences', String(out.summary.inferred_left_widths));
  }

  console.log('\n── Existing complete widths are preserved ──');
  {
    const samples = [sample(0, 6, 8), sample(1, 0, 9, 'one-sided', 0.4), sample(2, 7, 7), sample(3, 8, 6)];
    const out = inferMissingWidths(samples, { window: 3, minCompleteNeighbors: 2 });
    assert(out.samples[0].left_width_m === 6 && out.samples[0].right_width_m === 8, 'raw complete widths unchanged');
    assert(out.samples[0].left_inferred !== true && out.samples[0].right_inferred !== true, 'complete bin not marked inferred');
  }

  console.log('\n── Both missing remains missing ──');
  {
    const samples = [sample(0, 6, 8), sample(1, 0, 0, 'missing', 0), sample(2, 7, 7)];
    const out = inferMissingWidths(samples, { window: 2, minCompleteNeighbors: 2 });
    assert(out.samples[1].left_width_m === 0 && out.samples[1].right_width_m === 0, 'both-missing raw widths unchanged');
    assert(!out.samples[1].left_inferred && !out.samples[1].right_inferred, 'both-missing not inferred');
  }

  console.log('\n── Long one-sided run is not inferred ──');
  {
    const samples = [sample(0, 6, 8), sample(1, 6, 8)];
    for (let s = 2; s < 7; s++) samples.push(sample(s, 0, 9, 'one-sided', 0.4));
    samples.push(sample(7, 7, 7), sample(8, 8, 6));
    const out = inferMissingWidths(samples, { window: 8, maxRun: 3, minCompleteNeighbors: 2 });
    assert(out.summary.inferred_left_widths === 0, 'no inferred widths in long run', String(out.summary.inferred_left_widths));
    assert(out.samples.slice(2, 7).every(s => !s.left_inferred), 'long run bins not marked inferred');
  }

  console.log('\n── No local context is not inferred ──');
  {
    const samples = [sample(0, 6, 8), sample(1, 0, 9, 'one-sided', 0.4), sample(2, 0, 10, 'one-sided', 0.4)];
    const out = inferMissingWidths(samples, { window: 1, minCompleteNeighbors: 2 });
    assert(out.summary.inferred_left_widths === 0, 'not enough complete neighbors prevents inference');
  }

  console.log('\n── computeBoundaries integration and default unchanged ──');
  {
    const pathPoints = [0, 1, 2, 3].map(s => ({ s_m: s, x_m: 0, z_m: s, sample_count: 1 }));
    const profileSamples = [sample(0, 6, 8), sample(1, 0, 9, 'one-sided', 0.4), sample(2, 7, 7), sample(3, 8, 6)];
    const raw = computeBoundaries({ pathPoints, profileSamples, useSmooth: false });
    const inferred = computeBoundaries({ pathPoints, profileSamples, useSmooth: false, inferMissingWidths: true, inferMissingWidthsOptions: { window: 3, minCompleteNeighbors: 2 } });
    assert(approxEq(raw.left[1].width_m, 0), 'default left width remains zero', String(raw.left[1].width_m));
    assert(approxEq(raw.left[1].x_m, 0), 'default boundary remains at center path', String(raw.left[1].x_m));
    assert(approxEq(inferred.left[1].width_m, 5), 'inferred left width used for offset', String(inferred.left[1].width_m));
    assert(approxEq(inferred.left[1].x_m, -5), 'inferred boundary offset from center path', String(inferred.left[1].x_m));
    assert(inferred.left[1].status === 'inferred-one-sided', 'inferred point has low-confidence status', inferred.left[1].status);
    assert(inferred.left[1].inferred === true && inferred.left[1].inferred_side === 'left', 'inferred point carries metadata');
    assert(inferred.summary.inferred_left_widths === 1, 'boundary summary includes inferred left count', String(inferred.summary.inferred_left_widths));
  }

  console.log('\n── CLI --infer-missing-widths round trip ──');
  {
    const pathJson = tempPath('bwi-path', '.json');
    const profileJson = tempPath('bwi-profile', '.json');
    const outJson = tempPath('bwi-out', '.json');
    fs.writeFileSync(pathJson, JSON.stringify({ track_id: 'bwi', layout_id: 'default', bin_size_m: 1, points: [0, 1, 2, 3].map(s => ({ s_m: s, x_m: 0, z_m: s, sample_count: 1 })) }));
    fs.writeFileSync(profileJson, JSON.stringify({ track_id: 'bwi', layout_id: 'default', bin_size_m: 1, samples: [sample(0, 6, 8), sample(1, 0, 9, 'one-sided', 0.4), sample(2, 7, 7), sample(3, 8, 6)] }));
    const cli = spawnSync('node', [SCRIPT, '--path', pathJson, '--profile', profileJson, '--out', outJson, '--infer-missing-widths'], { encoding: 'utf8', timeout: 30000 });
    assert(cli.status === 0, 'CLI exits 0', cli.stderr);
    const disk = JSON.parse(fs.readFileSync(outJson, 'utf8'));
    assert(disk.summary.inferred_left_widths === 1, 'CLI output summary includes inferred left count', JSON.stringify(disk.summary));
    assert(disk.left[1].inferred === true, 'CLI output contains inferred boundary metadata');
  }
}

async function main() {
  console.log('═══ Track Outline Phase 09.3 Boundary Width Inference Tests ═══\n');
  await runTests();
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) throw new Error(`${failCount} assertions failed`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
