#!/usr/bin/env node
'use strict';
// @parallel true

/**
 * Static outline runtime rendering tests.
 *
 * Verifies that the static Spa outline data module and SVG rendering
 * produce correct output.
 *
 * Run: node scripts/test_static_outline_runtime_rendering.js
 */

const fs = require('fs');
const path = require('path');

let pass = 0;
let fail = 0;

function ok(condition, label) {
  if (condition) { pass++; console.log(`  [PASS] ${label}`); }
  else           { fail++; console.log(`  [FAIL] ${label}`); }
}

const ROOT = path.resolve(__dirname, '..', '..');
const sourcePath = path.join(ROOT, 'product', 'data', 'track-outlines', 'spa-francorchamps.json');
const runtimePath = path.join(ROOT, 'product', 'web', 'js', 'staticSpaOutlineData.js');

(async () => {
  const source = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));
  const { SPA_STATIC_OUTLINE } = await import(`${runtimePath}?t=${Date.now()}`);

  ok(SPA_STATIC_OUTLINE != null, 'SPA_STATIC_OUTLINE is exported');
  ok(typeof SPA_STATIC_OUTLINE === 'object', 'SPA_STATIC_OUTLINE is an object');

  // Deep-equal: source artifact matches runtime copy
  ok(JSON.stringify(SPA_STATIC_OUTLINE) === JSON.stringify(source),
    'runtime Spa outline data matches product/data/track-outlines source artifact');
  ok(SPA_STATIC_OUTLINE.schema_version === 1, 'runtime outline exposes schema v1');

  const modulePath = path.join(ROOT, 'product', 'web', 'js', 'staticTrackOutline.js');
  const { renderStaticTrackOutlineSvg } = await import(`${modulePath}?t=${Date.now()}`);
  const outline = SPA_STATIC_OUTLINE;

  const transform = { toMapX: x => x / 10, toMapZ: y => 250 - y / 10 };
  const svg = renderStaticTrackOutlineSvg(outline, transform);

  ok(svg.includes('data-static-track-outline="LMU Spa-Francorchamps"'), 'static outline group is identifiable');
  ok(svg.includes('data-static-outline-part="left_boundary"'), 'left boundary is rendered');
  ok(svg.includes('data-static-outline-part="right_boundary"'), 'right boundary is rendered');
  ok(svg.includes('data-static-outline-part="centerline"'), 'centerline is rendered');
  ok(svg.indexOf('left_boundary') < svg.indexOf('centerline'), 'boundaries render before centerline in the static group');

  const total = pass + fail;
  console.log(`\n  ${pass}/${total} assertions passed`);
  if (fail > 0) {
    console.log(`  ✔ ${fail} assertion(s) failed`);
    process.exit(1);
  }
  console.log('  ✔ All assertions passed');
})().catch(err => {
  console.error(err);
  process.exit(1);
});