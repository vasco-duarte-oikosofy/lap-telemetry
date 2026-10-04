#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Lap duration resolution in the web pipeline.
 *
 * Ground truth is the telemetry lap-start ET difference between consecutive
 * laps (TinyPedal method). The recorder stores
 * `session_time_s - lap_time_s == lmuTeleVeh.mLapStartET`, so the web can
 * recover it. Extracted reference laps additionally encode the exact duration
 * in the filename; a single-segment file cannot compute the diff itself.
 *
 * Run: node dev/scripts/test_reference_lap_duration.js
 */

const path = require('path');
const { pathToFileURL } = require('url');

let pass = 0, fail = 0;
function ok(condition, label) {
  if (condition) { pass++; console.log(`  [PASS] ${label}`); }
  else           { fail++; console.log(`  [FAIL] ${label}`); }
}

const ROOT = path.resolve(__dirname, '..', '..');
const pipelineUrl = pathToFileURL(path.join(ROOT, 'product', 'web', 'js', 'pipeline.js')).href;

// Synthetic single-lap reference file (Road Atlanta lap 15).
// Row 0 is the stale SHM boundary frame (negative lap_time_s, near-lap-end dist).
// max(lap_time_s) = 76.722 (last partial sample), true telemetry time = 76.809.
const DIST    = [4082.1, 5.7, 1000, 2500, 4081.5];
const LAP_T   = [-0.078, 10, 30, 55, 76.722];
const SESSION_T = [1625.6, 1635.678, 1655.678, 1680.678, 1702.400];
const SCORING = [77.466, 77.345, 77.345, 77.345, 77.345];
const REF_NAME = 'michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.16.809.parquet';
const SESSION_NAME = 'session_20261004T133118Z_michelin-raceway-road-atlanta_lmu_practice.parquet';

(async () => {
  const { annotateSegments, buildSegments } = await import(pipelineUrl);

  // Single segment, no filename: falls back to max(lap_time_s).
  const a = buildSegments([15, 15, 15, 15, 15]);
  annotateSegments(a, DIST, LAP_T, SCORING);
  ok(Math.abs(a[0].duration - 76.722) < 1e-6, 'single segment without filename falls back to max(lap_time_s)');

  // Single segment + reference filename: exact authoritative duration.
  const b = buildSegments([15, 15, 15, 15, 15]);
  annotateSegments(b, DIST, LAP_T, SCORING, REF_NAME);
  ok(Math.abs(b[0].duration - 76.809) < 1e-6, 'reference filename time (76.809) overrides lap_time_s');
  ok(b[0].durationSource === 'reference_lap_filename', 'durationSource marks reference_lap_filename');

  // Regular session filename must not be treated as a reference lap.
  const c = buildSegments([15, 15, 15, 15, 15]);
  annotateSegments(c, DIST, LAP_T, SCORING, SESSION_NAME);
  ok(Math.abs(c[0].duration - 76.722) < 1e-6, 'session filename does not override duration');

  // Two segments: telemetry lap-start diff is authoritative, even when the
  // scorer value (next segment) is a stale previous-lap time.
  const segs = buildSegments([5, 5, 5, 6, 6]);
  const dist2 = [0, 500, 1000, 0, 500];
  const lapT2 = [0, 10, 20.0, 0, 10];
  const sessT2 = [100, 110, 120, 120.5, 130.5]; // lap starts 100 and 120.5 => 20.5 s
  const scoring2 = [0, 0, 0, 21.0, 21.0];
  annotateSegments(segs, dist2, lapT2, scoring2, null, sessT2);
  ok(Math.abs(segs[0].duration - 20.5) < 1e-9,
    'two segments use telemetry lap-start diff, not stale scorer', `${segs[0].duration}`);
  ok(segs[0].durationSource === 'telemetry_lap_start', 'durationSource marks telemetry_lap_start');

  const total = pass + fail;
  console.log(`\n  ${pass}/${total} assertions passed`);
  if (fail > 0) process.exit(1);
  console.log('  ✔ All assertions passed');
})().catch(err => { console.error(err); process.exit(1); });
