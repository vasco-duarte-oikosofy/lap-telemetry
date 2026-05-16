/**
 * F16 Auto-Zoom — computeSegmentBounds unit tests.
 *
 * Run: node scripts/test_f16_segment_bounds.js
 */
// @parallel true

'use strict';

const { execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const SRC = path.join(ROOT, 'product', 'web', 'js', 'trackHeatmapMap.js');

// Bundle computeSegmentBounds via esbuild into a temp CJS file for testing
const TEMP_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'f16-segbounds-'));
const BUNDLED = path.join(TEMP_DIR, 'segmentBounds.cjs');

const ENTRY = path.join(TEMP_DIR, 'entry.mjs');
fs.writeFileSync(ENTRY, `export { computeSegmentBounds } from '${SRC.replace(/\\/g, '/')}';\n`);

execSync(
  `npx esbuild "${ENTRY}" --bundle --format=cjs --platform=node ` +
  `--outfile="${BUNDLED}" --external:./pipeline --external:./ribbon ` +
  `--external:./mapLegend --external:./trackHeatmapDrawing --external:./trackOutlineManifest`,
  { cwd: ROOT, stdio: 'pipe' }
);

const { computeSegmentBounds } = require(BUNDLED);

let passCount = 0;
let failCount = 0;
const results = [];

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  results.push({ status, name, detail: String(detail) });
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function approxEq(a, b, eps = 1e-10) {
  return Math.abs(a - b) < eps;
}

// ── Helper: create a simple lap with x along track, z varying ────────────────
// Track is 1000 m. x[i] = distance = i, z varies to make it interesting.
function makeLap(n) {
  const x = new Float64Array(n);
  const z = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    x[i] = i * (1000 / (n - 1)); // distance from 0 to 1000
    z[i] = Math.sin(i * 0.01) * 50 + Math.cos(i * 0.03) * 20; // some shape
  }
  return { x, z };
}

// ── Helper: track with flat z (horizontal line) ──────────────────────────────
function makeFlatLap(n) {
  const x = new Float64Array(n);
  const z = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    x[i] = i * (1000 / (n - 1));
    z[i] = 0;
  }
  return { x, z };
}

async function runTests() {
  console.log('═══ F16 — computeSegmentBounds Unit Tests ═══\n');

  // ── Test 1: Happy path — partial range returns tight bounds ─────────────
  console.log('\n════ SCENARIO 1: happy path — partial range ════');
  {
    const lap = makeLap(1001);
    const result = computeSegmentBounds(lap, { start: 200, end: 800 });

    assert(result !== null, 'returns non-null for partial range');
    if (result) {
      // minX should be at least 200 (start of range)
      assert(result.minX >= 200, 'minX >= 200', String(result.minX));
      assert(result.maxX <= 800, 'maxX <= 800', String(result.maxX));
      // minZ and maxZ should be within the z range of that segment
      assert(isFinite(result.minZ), 'minZ is finite', String(result.minZ));
      assert(isFinite(result.maxZ), 'maxZ is finite', String(result.maxZ));
    }
  }

  // ── Test 2: Full-track range returns null ───────────────────────────────
  console.log('\n════ SCENARIO 2: full-track range returns null ════');
  {
    const lap = makeLap(1001);
    const result = computeSegmentBounds(lap, { start: 0, end: 1000 });
    assert(result === null, 'full-track range (0→1000) returns null');
  }

  // ── Test 3: null visibleRange returns null ──────────────────────────────
  console.log('\n════ SCENARIO 3: null range returns null ════');
  {
    const lap = makeLap(1001);
    const result = computeSegmentBounds(lap, null);
    assert(result === null, 'null range returns null');
  }

  // ── Test 4: undefined visibleRange returns null ─────────────────────────
  console.log('\n════ SCENARIO 4: undefined range returns null ════');
  {
    const lap = makeLap(1001);
    const result = computeSegmentBounds(lap, undefined);
    assert(result === null, 'undefined range returns null');
  }

  // ── Test 5: Range beyond data returns null ─────────────────────────────
  console.log('\n════ SCENARIO 5: range beyond data returns null ════');
  {
    const lap = makeLap(1001); // distances 0→1000
    const result = computeSegmentBounds(lap, { start: 2000, end: 3000 });
    assert(result === null, 'range beyond data returns null');
  }

  // ── Test 6: Inverted range normalizes and returns bounds ────────────────
  console.log('\n════ SCENARIO 6: inverted range normalizes ════');
  {
    const lap = makeFlatLap(1001);
    // Range is inverted: start > end → should normalize
    const result = computeSegmentBounds(lap, { start: 800, end: 200 });
    assert(result !== null, 'inverted range returns non-null (normalized)');
    if (result) {
      // For flat lap (z=0), with x from 200 to 800
      assert(approxEq(result.minX, 200), 'minX ≈ 200 after normalization', String(result.minX));
      assert(approxEq(result.maxX, 800), 'maxX ≈ 800 after normalization', String(result.maxX));
      assert(approxEq(result.minZ, 0), 'minZ ≈ 0 for flat lap', String(result.minZ));
      assert(approxEq(result.maxZ, 0), 'maxZ ≈ 0 for flat lap', String(result.maxZ));
    }
  }

  // ── Test 7: Exact bounds for known geometry ──────────────────────────────
  console.log('\n════ SCENARIO 7: exact bounds for known geometry ════');
  {
    // Simple track: points at (0,0), (100,200), (200,0), (300,-100), (400,50)
    // Index i corresponds to distance i (resampled at 1m bins convention).
    const x = new Float64Array([0, 100, 200, 300, 400]);
    const z = new Float64Array([0, 200, 0, -100, 50]);
    const lap = { x, z };

    // Range covering indices 1–3 (distances 100–300 in resampled convention)
    const result = computeSegmentBounds(lap, { start: 1, end: 3 });
    assert(result !== null, 'partial range returns non-null');
    if (result) {
      assert(approxEq(result.minX, 100), 'minX = 100', String(result.minX));
      assert(approxEq(result.maxX, 300), 'maxX = 300', String(result.maxX));
      assert(approxEq(result.minZ, -100), 'minZ = -100 (point at z=-100)', String(result.minZ));
      assert(approxEq(result.maxZ, 200), 'maxZ = 200 (point at z=200)', String(result.maxZ));
    }
  }

  // ── Test 8: Range covering entire lap (loose bounds) returns null ───────
  console.log('\n════ SCENARIO 8: range just inside full track returns bounds ════');
  {
    const lap = makeFlatLap(1001);
    // Range from 0 to 999 — not quite full track (1000), so should return bounds
    const result = computeSegmentBounds(lap, { start: 0, end: 999 });
    assert(result !== null, 'near-full range returns non-null (not equal to full track)');
  }

  // ── Test 9: Empty lap returns null ──────────────────────────────────────
  console.log('\n════ SCENARIO 9: empty lap returns null ════');
  {
    const lap = { x: new Float64Array(0), z: new Float64Array(0) };
    const result = computeSegmentBounds(lap, { start: 0, end: 100 });
    assert(result === null, 'empty lap returns null');
  }

  // ── Test 10: Single-point range ─────────────────────────────────────────
  console.log('\n════ SCENARIO 10: single-point range ════');
  {
    const lap = makeFlatLap(1001);
    const result = computeSegmentBounds(lap, { start: 500, end: 500 });
    assert(result !== null, 'single-point range returns non-null');
    if (result) {
      assert(approxEq(result.minX, 500), 'minX = 500', String(result.minX));
      assert(approxEq(result.maxX, 500), 'maxX = 500', String(result.maxX));
    }
  }

  // ── Cleanup ─────────────────────────────────────────────────────────────
  try { fs.rmSync(TEMP_DIR, { recursive: true }); } catch {}

  // ── Report ───────────────────────────────────────────────────────────────
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount > 0) throw new Error(`${failCount} assertions failed`);
}

runTests().catch(err => {
  console.error(err);
  process.exit(1);
});