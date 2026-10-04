#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Reference-lap duration resolution.
 *
 * The recorder's max(lap_time_s) undercounts the authoritative lap time
 * (bug 13 legacy delta). For extracted reference laps the authoritative
 * duration is encoded in the filename: <...>_time_MM.SS.mmm.parquet.
 * annotateSegments() must prefer that over the lagging lap_time_s clock.
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
const DIST    = [4082.1, 5.7, 1000, 2500, 4081.5];
const LAP_T   = [-0.078, 10, 30, 55, 76.722];
const SCORING = [77.466, 77.345, 77.345, 77.345, 77.345];
const REF_NAME = 'michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.17.345.parquet';
const SESSION_NAME = 'session_20261004T133118Z_michelin-raceway-road-atlanta_lmu_practice.parquet';

(async () => {
  const { annotateSegments, buildSegments } = await import(pipelineUrl);

  // Bug baseline: no filename => lap_time_s fallback undercounts.
  const a = buildSegments([15, 15, 15, 15, 15]);
  annotateSegments(a, DIST, LAP_T, SCORING);
  ok(Math.abs(a[0].duration - 76.722) < 1e-6, 'no filename falls back to lap_time_s (documents bug)');

  // Fix: reference-lap filename is authoritative.
  const b = buildSegments([15, 15, 15, 15, 15]);
  annotateSegments(b, DIST, LAP_T, SCORING, REF_NAME);
  ok(Math.abs(b[0].duration - 77.345) < 1e-6, 'reference filename time (77.345) overrides lap_time_s');
  ok(b[0].durationSource === 'reference_lap_filename', 'durationSource marks reference_lap_filename');

  // A regular session filename must not be treated as a reference lap.
  const c = buildSegments([15, 15, 15, 15, 15]);
  annotateSegments(c, DIST, LAP_T, SCORING, SESSION_NAME);
  ok(Math.abs(c[0].duration - 76.722) < 1e-6, 'session filename does not override duration');

  const total = pass + fail;
  console.log(`\n  ${pass}/${total} assertions passed`);
  if (fail > 0) process.exit(1);
  console.log('  ✔ All assertions passed');
})().catch(err => { console.error(err); process.exit(1); });
